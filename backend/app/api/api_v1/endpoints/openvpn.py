from fastapi import APIRouter, Depends, HTTPException

from app.api.security import get_current_user
from app.services import openvpn
from app.services.importer import import_openvpn
from app.api import deps

router = APIRouter()


@router.get("/status")
def status(user=Depends(get_current_user)) -> dict[str, str]:
    # 查询 OpenVPN systemd 服务状态（超级管理员）
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    try:
        output = openvpn.service_action("status")
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"action": "status", "result": output}


@router.post("/{action}", summary="Control OpenVPN service (systemctl)")
def control_service(action: openvpn.ServiceAction, user=Depends(get_current_user)) -> dict[str, str]:
    # 控制 OpenVPN 服务：start/stop/restart/status（超级管理员）
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    try:
        output = openvpn.service_action(action)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"action": action, "result": output}


@router.post("/import", summary="Import local OpenVPN server and CCD clients")
def import_from_host(user=Depends(get_current_user), db=Depends(deps.get_db)) -> dict[str, int]:
    # 从本机 OpenVPN 配置导入服务器与 CCD 客户端（超级管理员）
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough privileges")
    try:
        stats = import_openvpn(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return stats
