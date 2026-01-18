import re
from pathlib import Path

from sqlalchemy.orm import Session

from app import crud
from app.core.config import get_settings
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
