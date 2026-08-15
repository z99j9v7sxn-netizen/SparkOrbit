"""模拟面试：会话 / 轮次 / 报告。"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    scenario: Mapped[str] = mapped_column(String(24), nullable=False, default="job")  # job | academic
    job_role: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    question_count: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="preparing", index=True
    )  # preparing | ready | running | scoring | completed | failed
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resume_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    resume_profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    questions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    prep_intel: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    assignment_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    prep_run_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    current_turn: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewTurn(Base):
    __tablename__ = "interview_turns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    question_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    audio_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    frame_urls: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prosody_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    visual_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fused_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prosody_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True, default=dict)
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    followup_of: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    followup_strategy: Mapped[str] = mapped_column(String(32), nullable=False, default="next")
    duration_sec: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InterviewPracticeRecord(Base):
    """练习舱：单题快练记录（不走完整会话/报告）。"""

    __tablename__ = "interview_practice_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    scenario: Mapped[str] = mapped_column(String(24), nullable=False, default="job")
    job_role: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    star_hit: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class InterviewApplication(Base):
    """求职助手：投递看板。"""

    __tablename__ = "interview_applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    company: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    portal_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="wishlist", index=True
    )  # wishlist | applied | oa | interview | offer | rejected
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class InterviewReport(Base):
    __tablename__ = "interview_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), index=True, unique=True, nullable=False)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    key_issues: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    suggestions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    resource_refs: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    council_views: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    teacher_comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    teacher_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    degraded_modalities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
