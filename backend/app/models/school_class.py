from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    invite_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
