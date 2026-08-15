"""考级中心：题库 / 试卷 / 模考 / 词书 / 打卡挑战。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base

EXAM_TYPES = ("cet4", "cet6", "ielts", "cantonese")
EXAM_SECTIONS = ("listening", "reading", "cloze", "translation", "writing", "vocab")


class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exam_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    section: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 客观题选项 {"A": "...", "B": "..."}；主观题为空
    options: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    analysis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 听力题的朗读原文（TTS 合成用）
    audio_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")  # ai | import
    created_by: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamPaper(Base):
    __tablename__ = "exam_papers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exam_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    # [{"section": "listening", "question_ids": [...]}, ...]
    structure: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="ai")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamMockRun(Base):
    __tablename__ = "exam_mock_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    paper_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    exam_type: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # {"listening": {"total": 10, "correct": 7}, ...}
    section_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ongoing")  # ongoing | done
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExamPracticeLog(Base):
    """专项刷题 / 打字 / 听写等训练记录（供周报与挑战统计）。"""

    __tablename__ = "exam_practice_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    exam_type: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    section: Mapped[str] = mapped_column(String(24), nullable=False, default="")
    activity: Mapped[str] = mapped_column(String(24), nullable=False, default="practice")  # practice | typing | dictation | essay
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExamWordEntry(Base):
    __tablename__ = "exam_word_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    exam_type: Mapped[str] = mapped_column(String(24), index=True, nullable=False)
    word: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    phonetic: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    meaning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    example: Mapped[str] = mapped_column(Text, nullable=False, default="")
    freq_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChallengeCampaignRecord(Base):
    """21 天打卡挑战：每用户一条参与记录。"""

    __tablename__ = "challenge_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="21 天备考挑战")
    exam_type: Mapped[str] = mapped_column(String(24), nullable=False, default="cet4")
    days_total: Mapped[int] = mapped_column(Integer, nullable=False, default=21)
    # 每日目标：{"words": 10, "questions": 5}
    daily_goal: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # ["2026-08-13", ...]
    checkins: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")  # active | done | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
