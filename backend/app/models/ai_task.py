from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AiTaskRecord(Base):
    __tablename__ = "ai_task_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="similar|grade")
    input_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
