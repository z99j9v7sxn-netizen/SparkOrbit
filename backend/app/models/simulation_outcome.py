"""预演 vs 真实作答对照落库。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, JSON, String, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SimulationOutcomeLink(Base):
    __tablename__ = "simulation_outcome_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    planet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    planet_slug: Mapped[str] = mapped_column(String(128), index=True, nullable=False, default="")
    sim_run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")
    predicted_weaknesses: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    real_challenge_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    real_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    agreement_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
