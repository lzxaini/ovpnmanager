from ipaddress import ip_network
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app import crud
from app.api import deps
from app.api.security import get_current_user
from app.core.config import get_settings
from app.schemas.server import Server, ServerCreate, ServerUpdate
from app.services import openvpn as openvpn_service
from app.services.importer import import_openvpn
from app.db.session import engine

settings = get_settings()

router = APIRouter(dependencies=[Depends(get_current_user)])


class ServerConfPayload(BaseModel):
    content: str


def ensure_server(db: Session) -> Server:
    """Single-server模式：如不存在则从本机配置导入/创建。"""
    try:
        servers = crud.server.get_multi(db, limit=1)
    except OperationalError as exc:
        if "vpnservers.vpn_ip" in str(exc):
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE vpnservers ADD COLUMN vpn_ip VARCHAR(50)"))
                conn.commit()
            servers = crud.server.get_multi(db, limit=1)
        else:
            raise
    if servers:
        return servers[0]
    import_openvpn(db)
    servers = crud.server.get_multi(db, limit=1)
    if servers:
        return servers[0]
    # 最后兜底创建占位
    return crud.server.create(
        db,
        ServerCreate(
            name="local",
            host="127.0.0.1",
            port=1194,
            protocol="tcp",
            status="unknown",
        ),
    )


def _status_from_output(output: str) -> str:
    text = output.lower()
    if "active: active (running)" in text or "active (running)" in text:
        return "running"
    if "inactive" in text or "dead" in text or "stopped" in text:
        return "stopped"
    return "unknown"


def _probe_status() -> str:
    try:
        output = openvpn_service.service_action("status")
        return _status_from_output(output)
    except Exception:
        return "unknown"


def _probe_vpn_ip() -> str | None:
    """Parse server.conf `server` 网段，返回网关 IP（network + 1）。"""
    conf_path = Path(settings.server_conf_path)
    if not conf_path.exists():
        return None
    for line in conf_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#"):
            continue
        if line.lower().startswith("server "):
            parts = line.split()
            if len(parts) >= 3:
                cidr = f"{parts[1]}/{parts[2]}"
                try:
                    net = ip_network(cidr, strict=False)
                    hosts = list(net.hosts())
                    if hosts:
                        return str(hosts[0])
                except Exception:
                    return None
    return None


@router.get("/", response_model=list[Server])
def list_servers(db: Session = Depends(deps.get_db)) -> list[Server]:
    # 单实例模式：返回唯一服务器信息
    server = ensure_server(db)
    server.status = _probe_status()
    server.vpn_ip = _probe_vpn_ip()
    return [server]


@router.post("/", response_model=Server, status_code=status.HTTP_201_CREATED)
def create_server(server_in: ServerCreate, db: Session = Depends(deps.get_db)) -> Server:
    # 禁止新增：单服务器模式
    raise HTTPException(status_code=400, detail="Single-server mode: creation disabled")


@router.patch("/{server_id}", response_model=Server)
def update_server(server_id: int, server_in: ServerUpdate, db: Session = Depends(deps.get_db)) -> Server:
    # 更新服务器信息
    db_obj = crud.server.get(db, server_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Server not found")
    return crud.server.update(db, db_obj=db_obj, obj_in=server_in)


@router.delete("/{server_id}", response_model=Server)
def delete_server(server_id: int, db: Session = Depends(deps.get_db)) -> Server:
    # 禁止删除：单服务器模式
    raise HTTPException(status_code=400, detail="Single-server mode: deletion disabled")


@router.get("/config", response_model=ServerConfPayload, dependencies=[Depends(get_current_user)])
def get_server_conf(_=Depends(get_current_user)) -> ServerConfPayload:
    """读取 server.conf 配置（登录即可查看）。"""
    conf_path = Path(settings.server_conf_path)
    if not conf_path.exists():
        raise HTTPException(status_code=404, detail="server.conf not found")
    return ServerConfPayload(content=conf_path.read_text())


@router.put("/config", response_model=ServerConfPayload, dependencies=[Depends(get_current_user)])
def update_server_conf(payload: ServerConfPayload, user=Depends(get_current_user)) -> ServerConfPayload:
    """更新 server.conf 配置（超级管理员）。"""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    conf_path = Path(settings.server_conf_path)
    conf_path.write_text(payload.content)
    return ServerConfPayload(content=payload.content)


@router.post("/control/{action}")
def control_server(action: openvpn_service.ServiceAction, user=Depends(get_current_user)) -> dict[str, str]:
    """控制 OpenVPN 服务 start/stop/restart/status（超级管理员）。"""
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    try:
        output = openvpn_service.service_action(action)
        status_text = _probe_status()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"action": action, "result": output, "status": status_text}
