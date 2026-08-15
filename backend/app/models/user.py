from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="未命名用户")
    avatar: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    avatar_cartoon_url: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="", comment="Qwen 卡通化 2D 图 URL"
    )
    avatar_model_url: Mapped[str] = mapped_column(
        String(1024), nullable=False, default="", comment="已废弃，保留列兼容旧数据"
    )
    class_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="所属班级")
    teacher_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", index=True, comment="负责老师")
    pet_slug: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="当前桌宠 slug")
    pet_affinity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="桌宠亲密度")
    equipped_title: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="佩戴称号")
    study_theme: Mapped[str] = mapped_column(String(64), nullable=False, default="", comment="自习室主题")
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="点亮积分")
    mood: Mapped[str] = mapped_column(String(32), nullable=False, default="calm", comment="分身心情")
    streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="连续学习天数")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="账号是否启用")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
