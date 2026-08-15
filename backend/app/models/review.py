"""间隔重复复习卡：词汇 / 自定义卡片的 SRS 调度状态。"""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ReviewCard(Base):
    __tablename__ = "review_cards"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    # word: 考级词汇 / 生词本；card: 自定义问答卡
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="card")
    # 来源标识（如词书条目 id、星库资产 id），用于去重
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    front: Mapped[str] = mapped_column(Text, nullable=False, default="")
    back: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 附加信息：音标/例句/学科等
    extra: Mapped[str] = mapped_column(Text, nullable=False, default="")
    interval_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_result: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
