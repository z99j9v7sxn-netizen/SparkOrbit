from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ResourceForumPost(Base):
    __tablename__ = "resource_forum_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    author_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    class_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="note")  # note | link | file
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")  # local | vault | workshop | video
    source_id: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promoted_asset_id: Mapped[str] = mapped_column(String(36), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
