from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class RemediationPlan(Base):
    __tablename__ = "remediation_plans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    simulation_run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    target_dimension: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    topic: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    root_cause: Mapped[str] = mapped_column(Text, nullable=False, default="")
    steps_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImprovementSubmission(Base):
    __tablename__ = "improvement_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    plan_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    reflection: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_bundle: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ai_grade: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    ai_feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ai_delta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    teacher_grade: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default=None)
    teacher_feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    final_grade: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    applied_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warning_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    teacher_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, default=None)
