import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import crud
from app.api import deps
from app.core.config import get_settings
from app.core.security import create_access_token, verify_password
from app.schemas.audit_log import AuditLogCreate
from app.schemas.token import Token

router = APIRouter()
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(deps.get_db)) -> Token:
    # 登录接口：验证用户名密码，签发访问 Token
    user = crud.user.get_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        try:
            crud.audit_log.create(
                db,
                AuditLogCreate(
                    actor=form_data.username,
                    action="user_login",
                    target=form_data.username,
                    result="fail",
                ),
            )
        except Exception:
            logger.exception("Failed to write audit log for login fail user=%s", form_data.username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if not user.is_active:
        try:
            crud.audit_log.create(
                db,
                AuditLogCreate(
                    actor=form_data.username,
                    action="user_login",
                    target=form_data.username,
                    result="fail",
                ),
            )
        except Exception:
            logger.exception("Failed to write audit log for inactive user login user=%s", form_data.username)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    access_token = create_access_token(
        subject=user.username, expires_delta=timedelta(minutes=settings.access_token_expire_minutes)
    )
    try:
        crud.audit_log.create(
            db,
            AuditLogCreate(
                actor=user.username,
                action="user_login",
                target=user.username,
                result="success",
            ),
        )
    except Exception:
        logger.exception("Failed to write audit log for login success user=%s", user.username)
    return Token(access_token=access_token)
