from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

DEFAULT_DECAY_DAYS = {"fading": 7, "meteor": 14, "dim": 30}


class GatePolicy(Base):
    """班级（可选星系）通关门控策略。"""

    __tablename__ = "gate_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    galaxy_slug: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")
    practice_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    practice_min_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    explain_pass_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    apply_required_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    learn_evidence_min: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    decay_days: Mapped[dict] = mapped_column(JSON, nullable=False, default=lambda: dict(DEFAULT_DECAY_DAYS))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
