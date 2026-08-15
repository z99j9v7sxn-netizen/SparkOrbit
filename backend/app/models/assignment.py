from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    galaxy_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 结构化题目列表：[{stem, options, answer, score, kind}]
    questions_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source_resource_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    assignment_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attachment_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    student_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    record_date: Mapped[str] = mapped_column(String(10), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="present")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class TeacherBroadcast(Base):
    __tablename__ = "teacher_broadcasts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recipient_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
