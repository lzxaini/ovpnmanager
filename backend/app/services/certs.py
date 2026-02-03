import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Tuple

from sqlalchemy.orm import Session

from app import crud
from app.core.config import get_settings
from app.models.client import Client
from app.schemas.certificate import CertificateCreate, CertificateUpdate


settings = get_settings()


def _run(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    """Run a command and raise with stderr if failed."""
    merged_env = None
    if env is not None:
        merged_env = os.environ.copy()
        merged_env.update(env)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=merged_env)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Command failed")
    return result.stdout


def _parse_cert_info(cert_path: Path) -> Tuple[str, datetime, datetime]:
    """Return (serial, not_before, not_after) for given cert."""
    out = _run(["openssl", "x509", "-in", str(cert_path), "-noout", "-serial", "-startdate", "-enddate"])
    serial = ""
    not_before = None
    not_after = None
    for line in out.splitlines():
        if line.startswith("serial="):
            serial = line.split("=", 1)[1].strip()
        elif line.startswith("notBefore="):
            not_before = datetime.strptime(line.split("=", 1)[1].strip(), "%b %d %H:%M:%S %Y %Z")
        elif line.startswith("notAfter="):
            not_after = datetime.strptime(line.split("=", 1)[1].strip(), "%b %d %H:%M:%S %Y %Z")
    if not serial or not_before is None or not_after is None:
        raise RuntimeError("Failed to parse certificate dates/serial")
    return serial, not_before, not_after


def build_client_cert(
    db: Session, client: Client, passwordless: bool = True, passphrase: str | None = None
) -> Path:
    """Generate (or reuse) client cert/key via EasyRSA and update certificate table."""
    cert_path = settings.easyrsa_path / "pki" / "issued" / f"{client.common_name}.crt"
    key_path = settings.easyrsa_path / "pki" / "private" / f"{client.common_name}.key"
    req_path = settings.easyrsa_path / "pki" / "reqs" / f"{client.common_name}.req"

    # If cert/key already exist, reuse them to avoid EasyRSA duplicate request errors
    if not (cert_path.exists() and key_path.exists()):
        # Clean stale req/key to avoid "already exists" errors on retries
        if req_path.exists():
            req_path.unlink()
        if key_path.exists() and not cert_path.exists():
            key_path.unlink()
        cmd = ["./easyrsa", "--batch", "build-client-full", client.common_name]
        if passwordless:
            cmd.append("nopass")
        env = None
        if passphrase:
            env = {"EASYRSA_PASSIN": f"pass:{passphrase}"}
        _run(cmd, cwd=settings.easyrsa_path, env=env)

    if not cert_path.exists() or not key_path.exists():
        raise RuntimeError("Client certificate or key not found after generation")

    serial, not_before, not_after = _parse_cert_info(cert_path)
    db_cert = crud.certificate.get_by_cn(db, common_name=client.common_name)
    if db_cert:
        crud.certificate.update(
            db,
            db_obj=db_cert,
            obj_in=CertificateUpdate(
                status="valid",
                revoked_at=None,
            ),
        )
        db_cert.serial_number = serial
        db_cert.not_before = not_before
        db_cert.not_after = not_after
    else:
        db_cert = crud.certificate.create(
            db,
            CertificateCreate(
                common_name=client.common_name,
                serial_number=serial,
                status="valid",
                not_before=not_before,
                not_after=not_after,
                revoked_at=None,
            ),
        )
    crud.client.update(db, db_obj=client, obj_in={"certificate_id": db_cert.id, "status": "offline"})
    return cert_path


def revoke_client_cert(db: Session, client: Client, passphrase: str | None = None) -> None:
    """Revoke client cert, generate CRL, update DB."""
    env = {"EASYRSA_PASSIN": f"pass:{passphrase}"} if passphrase else None
    _run(["./easyrsa", "--batch", "revoke", client.common_name], cwd=settings.easyrsa_path, env=env)
    _run(["./easyrsa", "gen-crl"], cwd=settings.easyrsa_path, env=env)

    crl_src = settings.easyrsa_path / "pki" / "crl.pem"
    settings.openvpn_crl_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(crl_src, settings.openvpn_crl_path)

    db_cert = crud.certificate.get_by_cn(db, common_name=client.common_name)
    if db_cert:
        crud.certificate.update(
            db,
            db_obj=db_cert,
            obj_in=CertificateUpdate(status="revoked", revoked_at=datetime.utcnow()),
        )
    crud.client.update(db, db_obj=client, obj_in={"status": "disabled"})


def _read_text(path: Path) -> str:
    return Path(path).read_text().strip()


def export_ovpn(client: Client, remote_host: str, remote_port: int) -> str:
    """Render inline .ovpn for the given client."""
    base = settings.easyrsa_path / "pki"
    cert_path = base / "issued" / f"{client.common_name}.crt"
    key_path = base / "private" / f"{client.common_name}.key"
    ca_path = settings.openvpn_base_path / "server" / "ca.crt"
    
    # Determine TLS auth mode and key path
    tls_mode = settings.tls_auth_mode
    if tls_mode == "tls-crypt-v2":
        tls_key_path = settings.tls_crypt_v2_key_path
    elif tls_mode == "tls-crypt":
        tls_key_path = settings.tls_crypt_key_path
    else:  # tls-auth
        tls_key_path = settings.ta_key_path

    for path in [cert_path, key_path, ca_path]:
        if not path.exists():
            raise RuntimeError(f"Required file missing: {path}")
    
    if not tls_key_path.exists():
        raise RuntimeError(f"TLS key file missing: {tls_key_path}")

    # Build TLS section based on mode
    if tls_mode == "tls-crypt-v2":
        # For tls-crypt-v2, generate client-specific key
        client_tls_key_path = base / "private" / f"{client.common_name}.tls-crypt-v2.key"
        if not client_tls_key_path.exists():
            try:
                _run([
                    "/usr/sbin/openvpn", "--tls-crypt-v2", str(tls_key_path),
                    "--genkey", "tls-crypt-v2-client", str(client_tls_key_path)
                ])
            except FileNotFoundError:
                # Fallback to PATH search
                _run([
                    "openvpn", "--tls-crypt-v2", str(tls_key_path),
                    "--genkey", "tls-crypt-v2-client", str(client_tls_key_path)
                ])
        tls_section = f"<tls-crypt-v2>\n{_read_text(client_tls_key_path)}\n</tls-crypt-v2>"
        key_direction = ""
    elif tls_mode == "tls-crypt":
        tls_section = f"<tls-crypt>\n{_read_text(tls_key_path)}\n</tls-crypt>"
        key_direction = ""
    else:  # tls-auth
        tls_section = f"<tls-auth>\n{_read_text(tls_key_path)}\n</tls-auth>"
        key_direction = "key-direction 1\n"

    template = f"""client
dev tun
proto tcp
remote {remote_host} {remote_port}
resolv-retry infinite
nobind
persist-key
persist-tun
remote-cert-tls server
cipher AES-256-GCM
auth SHA256
{key_direction}verb 3

<ca>
{_read_text(ca_path)}
</ca>
<cert>
{_read_text(cert_path)}
</cert>
<key>
{_read_text(key_path)}
</key>
{tls_section}
"""
    export_dir = settings.openvpn_client_export_path
    export_dir.mkdir(parents=True, exist_ok=True)
    (export_dir / f"{client.common_name}.ovpn").write_text(template)
    return template
