from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class PlanetMastery(Base):
    """学生对某颗行星的掌握状态（每人每行星一条）。"""

    __tablename__ = "planet_mastery"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    planet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="dim", comment="dim/lit/fading/meteor（locked 由前置动态计算）")
    mastery_phase: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default="dim",
        comment="dim/exploring/practicing/explaining/applying/lit",
    )
    gate_flags: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="learn/practice/explain/apply/apply_required",
    )
    learn_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="学闸证据列表")
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="最近一次得分 0-100")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_wrong_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="易错标签，反哺画像")
    fragments: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="知识碎片收集进度")
    lit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decay_state: Mapped[str] = mapped_column(String(16), nullable=False, default="lit", comment="lit/fading/meteor/dim")
    is_permanent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="超新星固化永久恒星")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChallengeQuestion(Base):
    """Teacher Agent 为某学生某行星生成的一道题目（服务端保存答案，防作弊）。"""

    __tablename__ = "challenge_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    planet_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="[{key,text}]")
    answer_key: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, comment="knowledge_point_id/traps/source_refs")
    answered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    selected_key: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
