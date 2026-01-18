from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base
from app.utils.time import now_shanghai_naive


class AuditLog(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    actor: Mapped[str] = mapped_column(String(100))
    action: Mapped[str] = mapped_column(String(200))
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    result: Mapped[str] = mapped_column(String(50), default="success")  # success/fail
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai_naive)
