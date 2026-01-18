import logging
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from pathlib import Path
from typing import Iterable

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.api.security import get_current_user
from app.core.config import get_settings
from app.schemas.client import Client, ClientCreate, ClientOnline, ClientPage, ClientUpdate
from app.schemas.audit_log import AuditLogCreate
from app.services import ccd as ccd_service
from app.services import certs, management, openvpn

settings = get_settings()
logger = logging.getLogger(__name__)


router = APIRouter(dependencies=[Depends(get_current_user)])


class OVPNResponse(BaseModel):
    ovpn: str


class ExportedCheckResponse(BaseModel):
    exists: bool
    ovpn: str | None = None


class BuildCertRequest(BaseModel):
    passphrase: str | None = None


class PassphrasePayload(BaseModel):
    passphrase: str | None = None


class ClientCreateRequest(ClientCreate):
    passphrase: str | None = None


class ClientValidateResponse(BaseModel):
    name_ok: bool = True
    common_name_ok: bool = True
    fixed_ip_ok: bool = True
    name_message: str | None = None
    common_name_message: str | None = None
    fixed_ip_message: str | None = None


def ensure_superuser(user=Depends(get_current_user)):
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    return user


def _safe_audit(db: Session, actor: str, action: str, target: str | None, result: str) -> None:
    try:
        crud.audit_log.create(
            db,
            AuditLogCreate(
                actor=actor,
                action=action,
                target=target,
                result=result,
            ),
        )
    except Exception:
        logger.exception("Failed to write audit log action=%s target=%s result=%s", action, target, result)


def _sync_client_status_and_audit(db: Session, *, online_common_names: Iterable[str]) -> None:
    online_set = set(online_common_names)
    changed = False
    clients = db.query(crud.client.model).all()
    for client in clients:
        desired_status = "online" if client.common_name in online_set else "offline"
        if client.disabled:
            desired_status = "disabled"
        if client.status != desired_status:
            prev_status = client.status
            client.status = desired_status
            changed = True
            if desired_status == "online":
                _safe_audit(db, actor="system", action="client_login", target=client.common_name, result="success")
            elif prev_status == "online" and desired_status != "online":
                _safe_audit(db, actor="system", action="client_logout", target=client.common_name, result="success")
    if changed:
        db.commit()


def _get_server_endpoint(db: Session) -> tuple[str, int]:
    servers = crud.server.get_multi(db, limit=1)
    if servers:
        s = servers[0]
        return s.host, s.port
    return "127.0.0.1", 1194


def _cleanup_client_files(common_name: str) -> None:
    """Remove exported ovpn and CCD file for the client, ignoring missing files."""
    export_path = settings.openvpn_client_export_path / f"{common_name}.ovpn"
    ccd_path = Path(settings.ccd_path) / common_name
    for path in (export_path, ccd_path):
        try:
            path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass
        except Exception:
            # best effort cleanup; avoid blocking API
            pass


def _load_server_network() -> IPv4Network | IPv6Network | None:
    conf_path = Path(settings.server_conf_path)
    if not conf_path.exists():
        return None
    for line in conf_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("server "):
            parts = line.split()
            if len(parts) >= 3:
                cidr = f"{parts[1]}/{parts[2]}"
                try:
                    return ip_network(cidr, strict=False)
                except Exception:
                    return None
    return None


def _validate_fields(
    db: Session,
    *,
    name: str | None,
    common_name: str | None,
    fixed_ip: str | None,
    require_all: bool,
    current_client_id: int | None = None,
):
    if require_all:
        if not name:
            raise HTTPException(status_code=400, detail="名称为必填项")
        if not common_name:
            raise HTTPException(status_code=400, detail="证书CN为必填项")
        if not fixed_ip:
            raise HTTPException(status_code=400, detail="固定IP为必填项")

    if name:
        existing = db.query(crud.client.model).filter(crud.client.model.name == name).first()
        if existing and existing.id != current_client_id:
            raise HTTPException(status_code=400, detail="名称已存在")
    if common_name:
        existing_cn = crud.client.get_by_common_name(db, common_name=common_name)
        if existing_cn and existing_cn.id != current_client_id:
            raise HTTPException(status_code=400, detail="证书CN已存在")

    if fixed_ip:
        try:
            ip = ip_address(fixed_ip)
        except ValueError as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="固定IP格式不合法") from exc

        net = _load_server_network()
        if net:
            if ip not in net or ip == net.network_address or ip == net.broadcast_address:
                raise HTTPException(status_code=400, detail="固定IP不在 server.conf 配置的网段内")
            # 避免与服务端占用的首个地址冲突
            host_iter = net.hosts()
            server_ip = next(host_iter, None)
            if server_ip and ip == server_ip:
                raise HTTPException(status_code=400, detail="固定IP不可与服务端地址重复")

        existing_ip = db.query(crud.client.model).filter(crud.client.model.fixed_ip == fixed_ip).first()
        if existing_ip and existing_ip.id != current_client_id:
            raise HTTPException(status_code=400, detail="固定IP已被其他客户端使用")


@router.get("/", response_model=ClientPage)
def list_clients(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=200),
    name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(deps.get_db),
) -> ClientPage:
    # 查询客户端列表（分页，仅需已登录），支持按名称与状态过滤，并融合在线状态
    try:
        online = {c.common_name: c for c in management.list_online()}
        _sync_client_status_and_audit(db, online_common_names=online.keys())
    except Exception:
        online = {}

    query = db.query(crud.client.model)
    if name:
        query = query.filter(crud.client.model.name.ilike(f"%{name}%"))
    if status:
        normalized_status = status.lower()
        if normalized_status in {"online", "offline", "disabled"}:
            query = query.filter(crud.client.model.status == normalized_status)

    total = query.count()
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()

    merged: list[Client] = []
    for item in items:
        item_status = item.status or "offline"
        if item.common_name in online:
            item_status = "online"
        item.status = item_status
        merged.append(item)
    return ClientPage(items=merged, total=total, page=page, page_size=page_size)


@router.post("/", response_model=Client, status_code=status.HTTP_201_CREATED)
def create_client(
    client_in: ClientCreateRequest, db: Session = Depends(deps.get_db), user=Depends(get_current_user)
) -> Client:
    # 创建客户端：先写入数据库，如证书生成失败则回滚删除
    logger.info("Creating client cn=%s by user=%s", client_in.common_name, getattr(user, "username", "unknown"))
    _validate_fields(
        db,
        name=client_in.name,
        common_name=client_in.common_name,
        fixed_ip=client_in.fixed_ip,
        require_all=True,
    )
    payload = ClientCreate(**client_in.model_dump(exclude={"passphrase"}))
    created = crud.client.create(db, payload)
    if client_in.fixed_ip is not None or client_in.routes is not None:
        routes = []
        if client_in.routes:
            routes = [r.strip() for r in client_in.routes.split(",") if r.strip()]
        ccd_service.write_ccd(created, fixed_ip=client_in.fixed_ip, routes=routes)
    try:
        certs.build_client_cert(db, created, passphrase=client_in.passphrase)
        host, port = _get_server_endpoint(db)
        if settings.public_ip:
            host = settings.public_ip
        if settings.public_port:
            port = settings.public_port
        # 生成并落盘 .ovpn（与下载逻辑一致），便于后续直接下载
        certs.export_ovpn(created, remote_host=host, remote_port=port)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to build cert during client create cn=%s", client_in.common_name)
        try:
            crud.client.remove(db, created.id)
            _cleanup_client_files(created.common_name)
        except Exception:
            logger.exception("Cleanup failed after create rollback cn=%s", client_in.common_name)
        raise HTTPException(status_code=500, detail=f"Failed to generate certificate: {exc}") from exc
    try:
        crud.audit_log.create(
            db,
            AuditLogCreate(
                actor=getattr(user, "username", "unknown"),
                action="create_client",
                target=client_in.common_name,
                result="success",
            ),
        )
    except Exception:
        # do not block client creation on audit failure
        logger.exception("Failed to write audit log for client create cn=%s", client_in.common_name)
    return created


@router.get("/validate", response_model=ClientValidateResponse)
def validate_client(
    name: str | None = Query(default=None),
    common_name: str | None = Query(default=None),
    fixed_ip: str | None = Query(default=None),
    db: Session = Depends(deps.get_db),
) -> ClientValidateResponse:
    """校验名称/证书CN/固定IP 可用性，不修改数据。"""
    resp = ClientValidateResponse()

    if name:
        exists = db.query(crud.client.model).filter(crud.client.model.name == name).first()
        if exists:
            resp.name_ok = False
            resp.name_message = "名称已存在"
        else:
            resp.name_message = "名称可用"

    if common_name:
        exists = crud.client.get_by_common_name(db, common_name=common_name)
        if exists:
            resp.common_name_ok = False
            resp.common_name_message = "证书CN已存在"
        else:
            resp.common_name_message = "证书CN可用"

    if fixed_ip:
        try:
            ip = ip_address(fixed_ip)
        except ValueError:
            resp.fixed_ip_ok = False
            resp.fixed_ip_message = "固定IP格式不合法"
        else:
            net = _load_server_network()
            if net and (ip not in net or ip == net.network_address or ip == net.broadcast_address):
                resp.fixed_ip_ok = False
                resp.fixed_ip_message = "固定IP不在 server.conf 网段内"
            else:
                host_iter = net.hosts() if net else iter(())
                server_ip = next(host_iter, None)
                if server_ip and ip == server_ip:
                    resp.fixed_ip_ok = False
                    resp.fixed_ip_message = "固定IP不可与服务端地址重复"
            if resp.fixed_ip_ok:
                exists_ip = db.query(crud.client.model).filter(crud.client.model.fixed_ip == fixed_ip).first()
                if exists_ip:
                    resp.fixed_ip_ok = False
                    resp.fixed_ip_message = "固定IP已被其他客户端使用"
                else:
                    resp.fixed_ip_message = "固定IP可用"

    return resp


@router.patch("/{client_id}", response_model=Client)
def update_client(client_id: int, client_in: ClientUpdate, db: Session = Depends(deps.get_db)) -> Client:
    # 更新客户端信息；如有固定 IP 或路由则写 CCD
    db_obj = crud.client.get(db, client_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Client not found")
    updated = crud.client.update(db, db_obj=db_obj, obj_in=client_in)
    # optional: write CCD when fixed_ip/routes provided
    if client_in.fixed_ip is not None or client_in.routes is not None:
        routes = []
        if client_in.routes:
            routes = [r.strip() for r in client_in.routes.split(",") if r.strip()]
        ccd_service.write_ccd(updated, fixed_ip=client_in.fixed_ip, routes=routes)
    return updated


@router.delete("/{client_id}", response_model=Client)
def delete_client(
    client_id: int, payload: PassphrasePayload | None = Body(default=None), db: Session = Depends(deps.get_db)
) -> Client:
    # 删除客户端记录
    db_obj = crud.client.get(db, client_id)
    if not db_obj:
        raise HTTPException(status_code=404, detail="Client not found")
    logger.info("Deleting client_id=%s cn=%s", client_id, db_obj.common_name)
    export_path = settings.openvpn_client_export_path / f"{db_obj.common_name}.ovpn"
    # 只有检测到已有导出的 .ovpn（意味着已生成证书）才吊销并刷新 CRL
    if export_path.exists():
        revoked = False
        try:
            passphrase = payload.passphrase if payload else None
            certs.revoke_client_cert(db, db_obj, passphrase=passphrase)
            revoked = True
        except Exception:
            logger.exception("Failed to revoke cert during delete for cn=%s", db_obj.common_name)
        if revoked:
            try:
                openvpn.service_action("restart")
            except Exception:
                logger.exception("OpenVPN restart failed after revoke for cn=%s", db_obj.common_name)
    removed = crud.client.remove(db, client_id)
    if removed:
        _cleanup_client_files(removed.common_name)
        try:
            crud.audit_log.create(
                db,
                AuditLogCreate(
                    actor="system",
                    action="delete_client",
                    target=removed.common_name,
                    result="success",
                ),
            )
        except Exception:
            logger.exception("Failed to write audit log for delete client cn=%s", removed.common_name)
    return removed


@router.get("/online", response_model=list[ClientOnline])
def list_online_clients(db: Session = Depends(deps.get_db), _=Depends(ensure_superuser)) -> list[ClientOnline]:
    # 查询在线客户端（需开启 management 接口）
    online_clients = management.list_online()
    try:
        _sync_client_status_and_audit(db, online_common_names=[c.common_name for c in online_clients])
    except Exception:
        # status sync best-effort
        logger.exception("Failed to sync client status/audit from online list")
    return [ClientOnline(**c.__dict__) for c in online_clients]


@router.post("/{client_id}/cert", response_model=OVPNResponse, dependencies=[Depends(ensure_superuser)])
def generate_client_cert(
    client_id: int, payload: BuildCertRequest | None = Body(default=None), db: Session = Depends(deps.get_db)
) -> OVPNResponse:
    # 生成客户端证书并导出 .ovpn（超级管理员）
    client = crud.client.get(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    passphrase = payload.passphrase if payload else None
    logger.info("Generating cert for client_id=%s cn=%s", client_id, client.common_name)
    certs.build_client_cert(db, client, passphrase=passphrase)
    host, port = _get_server_endpoint(db)
    # override remote host/port if public_* provided in settings
    if settings.public_ip:
        host = settings.public_ip
    if settings.public_port:
        port = settings.public_port
    ovpn = certs.export_ovpn(client, remote_host=host, remote_port=port)
    logger.info("Exported ovpn for client_id=%s cn=%s", client_id, client.common_name)
    return OVPNResponse(ovpn=ovpn)


@router.get("/{client_id}/cert/exported", response_model=ExportedCheckResponse, dependencies=[Depends(ensure_superuser)])
def check_exported_client_cert(client_id: int, db: Session = Depends(deps.get_db)) -> ExportedCheckResponse:
    """检查是否已有导出的 .ovpn，若存在则直接返回内容。"""
    client = crud.client.get(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    export_path = settings.openvpn_client_export_path / f"{client.common_name}.ovpn"
    if export_path.exists():
        try:
            logger.info("Existing ovpn found for client_id=%s cn=%s", client_id, client.common_name)
            return ExportedCheckResponse(exists=True, ovpn=export_path.read_text())
        except Exception:
            logger.exception("Failed to read existing ovpn for client_id=%s cn=%s", client_id, client.common_name)
            return ExportedCheckResponse(exists=True, ovpn=None)
    return ExportedCheckResponse(exists=False, ovpn=None)


@router.post("/{client_id}/revoke", dependencies=[Depends(ensure_superuser)])
def revoke_client_cert(
    client_id: int, payload: PassphrasePayload | None = Body(default=None), db: Session = Depends(deps.get_db)
) -> dict[str, str]:
    # 吊销客户端证书并刷新 CRL（超级管理员）
    client = crud.client.get(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    passphrase = payload.passphrase if payload else None
    logger.info("Revoking cert for client_id=%s cn=%s", client_id, client.common_name)
    certs.revoke_client_cert(db, client, passphrase=passphrase)
    try:
        openvpn.service_action("restart")
    except Exception as exc:
        logger.exception("OpenVPN restart failed after revoke for cn=%s", client.common_name)
        raise HTTPException(status_code=500, detail=f"Revoke succeeded but restart failed: {exc}") from exc
    return {"detail": "revoked"}


@router.post("/{client_id}/disconnect", dependencies=[Depends(ensure_superuser)])
def disconnect_client(
    client_id: int, db: Session = Depends(deps.get_db), user=Depends(get_current_user)
) -> dict[str, str]:
    # 通过 management 接口踢下线（超级管理员）
    client = crud.client.get(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    try:
        management.disconnect(client.common_name)
        logger.info("Disconnected client via management cn=%s", client.common_name)
        try:
            crud.audit_log.create(
                db,
                AuditLogCreate(
                    actor=getattr(user, "username", "unknown"),
                    action="client_disconnect",
                    target=client.common_name,
                    result="success",
                ),
            )
        except Exception:
            logger.exception("Failed to write audit log for disconnect cn=%s", client.common_name)
    except Exception as exc:  # pragma: no cover - management errors
        logger.exception("Failed to disconnect client cn=%s", client.common_name)
        try:
            crud.audit_log.create(
                db,
                AuditLogCreate(
                    actor=getattr(user, "username", "unknown"),
                    action="client_disconnect",
                    target=client.common_name,
                    result="fail",
                ),
            )
        except Exception:
            logger.exception("Failed to write audit log for disconnect fail cn=%s", client.common_name)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"detail": "disconnected"}


@router.patch("/{client_id}/ccd", response_model=Client, dependencies=[Depends(ensure_superuser)])
def update_ccd(client_id: int, client_in: ClientUpdate, db: Session = Depends(deps.get_db)) -> Client:
    # 写 CCD：静态 IP 与路由（超级管理员）
    client = crud.client.get(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    routes = []
    if client_in.routes:
        routes = [r.strip() for r in client_in.routes.split(",") if r.strip()]
    updated = crud.client.update(db, db_obj=client, obj_in=client_in)
    ccd_service.write_ccd(updated, fixed_ip=client_in.fixed_ip, routes=routes)
    return updated
