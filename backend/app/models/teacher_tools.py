"""教师端扩展：题库 / 私信 / 分组 / 激励 / 教学日历。"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class QuestionBankItem(Base):
    """教师题库：沉淀可复用题目（手动/AI 生成/作业收藏）。"""

    __tablename__ = "question_bank_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    stem: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="choice", comment="choice/short/judge")
    options: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    answer: Mapped[str] = mapped_column(Text, nullable=False, default="")
    explanation: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    galaxy_slug: Mapped[str] = mapped_column(String(128), index=True, nullable=False, default="")
    planet_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual", comment="manual/ai/assignment")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class DirectMessage(Base):
    """师生一对一私信（教师发送为主，落学生通知中心）。"""

    __tablename__ = "direct_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    sender_role: Mapped[str] = mapped_column(String(16), nullable=False, default="teacher")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudentGroup(Base):
    """班内学习小组：按组派发任务与干预。"""

    __tablename__ = "student_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    member_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    note: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PraiseRecord(Base):
    """教师激励：表扬 / 徽章 / 积分发放记录。"""

    __tablename__ = "praise_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    badge: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TeacherCalendarEvent(Base):
    """教学日历自定义事件（作业截止由 assignments 动态合并）。"""

    __tablename__ = "teacher_calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    event_date: Mapped[str] = mapped_column(String(10), index=True, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(24), nullable=False, default="custom", comment="custom/exam/lesson/meeting")
    note: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
