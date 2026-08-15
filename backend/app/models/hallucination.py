"""低置信判题 / 引用不一致时的教师待审工单。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class HallucinationTicket(Base):
    __tablename__ = "hallucination_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    student_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    challenge_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    planet_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    planet_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    knowledge_point_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    cited_knowledge_point_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reason: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    question_preview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")  # pending/resolved
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
