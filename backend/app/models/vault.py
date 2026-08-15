"""星轨知识库（Obsidian 兼容 Vault）元数据。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudentVault(Base):
    __tablename__ = "student_vaults"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, nullable=False)
    vault_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VaultFile(Base):
    __tablename__ = "vault_files"
    __table_args__ = (UniqueConstraint("user_id", "path", name="uq_vault_file_user_path"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    frontmatter_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class VaultLink(Base):
    __tablename__ = "vault_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    from_path: Mapped[str] = mapped_column(String(512), nullable=False, default="", index=True)
    to_path: Mapped[str] = mapped_column(String(512), nullable=False, default="", index=True)
    to_exists: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    link_type: Mapped[str] = mapped_column(String(24), nullable=False, default="wiki")  # wiki/embed/tag
