from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.api.security import get_current_user
from app.schemas.audit_log import AuditLogPage

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/audit", response_model=AuditLogPage, summary="List audit logs with pagination")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: str | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    db: Session = Depends(deps.get_db),
) -> AuditLogPage:
    query = db.query(crud.audit_log.model)
    if action:
        query = query.filter(crud.audit_log.model.action == action)
    if start_time:
        query = query.filter(crud.audit_log.model.created_at >= start_time)
    if end_time:
        query = query.filter(crud.audit_log.model.created_at <= end_time)

    total = query.count()
    offset = (page - 1) * page_size
    items = query.order_by(crud.audit_log.model.created_at.desc()).offset(offset).limit(page_size).all()
    return AuditLogPage(items=items, total=total, page=page, page_size=page_size)
