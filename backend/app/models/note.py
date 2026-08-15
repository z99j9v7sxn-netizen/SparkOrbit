from datetime import datetime, timezone

from sqlalchemy import DateTime, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    planet_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    galaxy_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attachment_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    blocks_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class LessonResource(Base):
    __tablename__ = "lesson_resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    teacher_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    galaxy_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    # book|deck|quiz|plan|other — 教师知识库分类
    resource_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="other")
    promoted_asset_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
