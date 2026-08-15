"""星库资产：教材 / PDF / 题库文档 / B站 / 自研视频。

存储约定（勿改为 MySQL BLOB）：
- 本表只存元数据（标题、类型、归属、状态、路径/外链等）
- PDF / 本地视频二进制落在 uploads/ 或 static/media/，本表 file_url 存可访问路径
- B 站视频只存 bilibili_bvid（及 meta_json 中的 embed），不下载进库
- PDF 抽取文本进 ChromaDB，不进本表正文
"""
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StarAsset(Base):
    __tablename__ = "star_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    asset_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pdf",
        comment="book/pdf/problem_doc/video_local/video_bilibili/note_pack",
    )
    galaxy_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="", index=True)
    planet_slug: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 路径或外链 URL，例如 /static/uploads/starlib/xxx.mp4；禁止存文件二进制
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    bilibili_bvid: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ready", comment="parsing/ready/failed")
    owner_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    class_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True)
    meta_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )
