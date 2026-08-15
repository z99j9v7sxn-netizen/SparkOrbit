from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

PROFILE_DIMENSIONS = (
    "major_background",
    "prior_knowledge",
    "cognitive_style",
    "mistake_tendency",
    "learning_goal",
    "time_flexibility",
    "modality_preference",
    "motivation_level",
)

DIMENSION_LABELS = {
    "major_background": "专业背景",
    "prior_knowledge": "前置知识",
    "cognitive_style": "认知风格",
    "mistake_tendency": "易错倾向",
    "learning_goal": "学习目标",
    "time_flexibility": "时间弹性",
    "modality_preference": "资源模态偏好",
    "motivation_level": "学习动机强度",
}


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    student_name: Mapped[str] = mapped_column(String(128), nullable=False, default="星轨学习者")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    major_background: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    prior_knowledge: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    cognitive_style: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    mistake_tendency: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    learning_goal: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    time_flexibility: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    modality_preference: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    motivation_level: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    missing_dimensions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    follow_up_questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    dimension_floors_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    warnings_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    update_source: Mapped[str] = mapped_column(String(32), nullable=False, default="profiler")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )