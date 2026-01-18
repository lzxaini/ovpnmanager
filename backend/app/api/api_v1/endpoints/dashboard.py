from datetime import datetime

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.api.security import get_current_user
from app.services import management, openvpn as openvpn_service

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


def _status_from_output(output: str) -> str:
    text = output.lower()
    if "active: active (running)" in text or "active (running)" in text:
        return "running"
    if "inactive" in text or "dead" in text or "stopped" in text:
        return "stopped"
    return "unknown"


@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(deps.get_db)) -> dict:
    """汇总仪表盘需要的实时/统计数据。"""
    logger.info("Dashboard metrics requested")
    total_clients = db.query(crud.client.model).count()
    try:
        online_clients = len(management.list_online())
    except Exception:
        logger.exception("Failed to list online clients via management")
        online_clients = 0

    cert_model = crud.certificate.model
    cert_total = db.query(func.count()).select_from(cert_model).scalar() or 0
    valid_count = db.query(func.count()).select_from(cert_model).filter(cert_model.status == "valid").scalar() or 0
    revoked_count = (
        db.query(func.count()).select_from(cert_model).filter(cert_model.status == "revoked").scalar() or 0
    )
    # 如果未及时标记过期，按 not_after 兜底统计一次
    expired_count = (
        db.query(func.count()).select_from(cert_model).filter(cert_model.not_after < datetime.utcnow()).scalar() or 0
    )

    openvpn_status = "unknown"
    try:
        output = openvpn_service.service_action("status")
        openvpn_status = _status_from_output(output)
    except Exception:
        logger.exception("Failed to probe openvpn service status")
        openvpn_status = "unknown"

    try:
        status_details = management.status_details()
    except Exception:
        logger.exception("Failed to read management status details")
        status_details = None

    load_stats = None
    try:
        load_stats = management.load_stats()
    except Exception:
        logger.debug("load-stats not supported or failed", exc_info=True)
        load_stats = None

    state_events = []
    try:
        state_events = management.state_history(limit=10)
    except Exception:
        logger.debug("state history not available", exc_info=True)
        state_events = []

    routing_table = []
    global_stats = {}
    if status_details:
        routing_table = [
            {
                "virtual_address": r.virtual_address,
                "real_address": r.real_address,
                "last_ref": r.last_ref,
                "common_name": r.common_name,
            }
            for r in status_details.routing_table
        ]
        global_stats = status_details.global_stats

    load_stats_dict = (
        {
            "nclients": load_stats.nclients,
            "bytes_in": load_stats.bytes_in,
            "bytes_out": load_stats.bytes_out,
            "uptime": load_stats.uptime,
        }
        if load_stats
        else None
    )

    state_events_dict = [
        {
            "timestamp": e.timestamp,
            "state": e.state,
            "detail": e.detail,
            "virtual_address": e.virtual_address,
            "common_name": e.common_name,
            "real_address": e.real_address,
        }
        for e in state_events
    ]

    recent_logs = [
        {
            "actor": log.actor,
            "action": log.action,
            "target": log.target,
            "result": log.result,
            "created_at": log.created_at.isoformat(),
        }
        for log in crud.audit_log.get_recent(db, limit=10)
    ]

    return {
        "online_clients": online_clients,
        "total_clients": total_clients,
        "certificates": {
            "total": cert_total,
            "valid": valid_count,
            "revoked": revoked_count,
            "expired": expired_count,
        },
        "openvpn": {
            "status": openvpn_status,
            "title": status_details.title if status_details else None,
            "time_unix": status_details.time_unix if status_details else None,
            "time_str": status_details.time_str if status_details else None,
            "global_stats": global_stats,
            "routing_table": routing_table,
            "load_stats": load_stats_dict,
            "state_events": state_events_dict,
        },
        # 目前暂无告警系统，占位返回 0
        "alerts": {"count": 0},
        "recent_activity": recent_logs,
    }
