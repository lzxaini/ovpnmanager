import re
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app import crud
from app.core.config import get_settings
from app.schemas.certificate import CertificateCreate
from app.schemas.client import ClientCreate, ClientUpdate
from app.schemas.server import ServerCreate, ServerUpdate

settings = get_settings()


def _parse_server_conf(conf_path: Path) -> dict:
    data: dict[str, str] = {}
    if not conf_path.exists():
        return data
    port_re = re.compile(r"^\s*port\s+(\d+)", re.I)
    proto_re = re.compile(r"^\s*proto\s+(tcp|udp)", re.I)
    for line in conf_path.read_text().splitlines():
        if m := port_re.match(line):
            data["port"] = m.group(1)
        if m := proto_re.match(line):
            data["protocol"] = m.group(1).lower()
    return data


def import_openvpn(db: Session, *, server_name: str = "local") -> dict[str, int]:
    created = 0
    updated = 0

    # server info
    conf_path = settings.openvpn_base_path / "server.conf"
    parsed = _parse_server_conf(conf_path)
    server_in = ServerCreate(
        name=server_name,
        host="127.0.0.1",
        port=int(parsed.get("port", 1194)),
        protocol=parsed.get("protocol", "tcp"),
        status="unknown",
    )
    existing_server = crud.server.get_by_name(db, name=server_name)
    if existing_server:
        crud.server.update(
            db,
            db_obj=existing_server,
            obj_in=ServerUpdate(
                host=server_in.host,
                port=server_in.port,
                protocol=server_in.protocol,
                status=server_in.status,
            ),
        )
        updated += 1
    else:
        crud.server.create(db, server_in)
        created += 1

    # CCD clients
    ccd_dir = Path(settings.ccd_path)
    if ccd_dir.exists():
        ip_re = re.compile(r"ifconfig-push\s+(\S+)\s+(\S+)", re.I)
        for ccd_file in ccd_dir.iterdir():
            if not ccd_file.is_file():
                continue
            cn = ccd_file.name
            fixed_ip = None
            routes = []
            for line in ccd_file.read_text().splitlines():
                if m := ip_re.search(line):
                    fixed_ip = m.group(1)
            # future: parse per-client routes
            db_client = crud.client.get_by_common_name(db, common_name=cn)
            if db_client:
                crud.client.update(
                    db,
                    db_obj=db_client,
                    obj_in=ClientUpdate(fixed_ip=fixed_ip, routes=",".join(routes) if routes else None),
                )
                updated += 1
            else:
                crud.client.create(
                    db,
                    ClientCreate(
                        name=cn,
                        common_name=cn,
                        fixed_ip=fixed_ip,
                        routes=",".join(routes) if routes else None,
                        status="offline",
                        disabled=False,
                    ),
                )
                created += 1

    return {"created": created, "updated": updated}


def import_certificates_from_easyrsa(db: Session) -> dict[str, int]:
    """
    从 Easy-RSA PKI 目录导入所有已颁发的证书到数据库
    适配 angristan 脚本: /etc/openvpn/server/easy-rsa/pki/issued/
    """
    created = 0
    skipped = 0
    errors = []

    easyrsa_pki = Path(settings.easyrsa_path) / "pki"
    issued_dir = easyrsa_pki / "issued"

    if not issued_dir.exists():
        return {
            "created": 0,
            "skipped": 0,
            "error": f"Easy-RSA PKI 目录不存在: {issued_dir}",
        }

    # 遍历所有 .crt 文件
    for cert_file in issued_dir.glob("*.crt"):
        cn = cert_file.stem  # 文件名即为 Common Name
        
        # 跳过服务器证书
        if cn in ["server", "Server"]:
            continue

        try:
            # 检查是否已存在
            existing_cert = crud.certificate.get_by_cn(db, common_name=cn)
            if existing_cert:
                skipped += 1
                continue

            # 读取证书信息
            cert_info = _get_cert_info(cert_file)
            if not cert_info:
                errors.append(f"无法读取证书: {cn}")
                continue

            # 创建证书记录
            cert_create = CertificateCreate(
                common_name=cn,
                serial_number=cert_info.get("serial", ""),
                not_before=cert_info.get("not_before"),
                not_after=cert_info.get("not_after"),
                status="valid",
            )
            crud.certificate.create(db, cert_create)

            # 检查或创建对应的客户端记录
            existing_client = crud.client.get_by_common_name(db, common_name=cn)
            if not existing_client:
                crud.client.create(
                    db,
                    ClientCreate(
                        name=cn,
                        common_name=cn,
                        status="offline",
                        disabled=False,
                    ),
                )

            created += 1

        except Exception as e:
            errors.append(f"{cn}: {str(e)}")
            continue

    result = {
        "created": created,
        "skipped": skipped,
    }
    if errors:
        result["errors"] = errors

    return result


def _get_cert_info(cert_path: Path) -> dict | None:
    """使用 openssl 读取证书信息"""
    try:
        # 获取序列号
        serial_result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-serial"],
            capture_output=True,
            text=True,
            check=True,
        )
        serial = serial_result.stdout.strip().split("=")[-1]

        # 获取起始日期
        startdate_result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-startdate"],
            capture_output=True,
            text=True,
            check=True,
        )
        startdate_str = startdate_result.stdout.strip().split("=", 1)[-1]
        
        # 获取过期日期
        enddate_result = subprocess.run(
            ["openssl", "x509", "-in", str(cert_path), "-noout", "-enddate"],
            capture_output=True,
            text=True,
            check=True,
        )
        enddate_str = enddate_result.stdout.strip().split("=", 1)[-1]

        # 解析日期 (格式: Jan  3 06:30:45 2026 GMT)
        issued_at = datetime.strptime(startdate_str, "%b %d %H:%M:%S %Y %Z")
        expires_at = datetime.strptime(enddate_str, "%b %d %H:%M:%S %Y %Z")

        return {
            "serial": serial,
            "not_before": issued_at,
            "not_after": expires_at,
        }
    except Exception:
        return None

