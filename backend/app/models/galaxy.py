from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Galaxy(Base):
    """星系 = 学科。整个宇宙由多个星系组成。"""

    __tablename__ = "galaxies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#2779a7", comment="星系主题色")
    orbit_radius: Mapped[float] = mapped_column(Float, nullable=False, default=12.0, comment="星系在宇宙中的轨道半径")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Planet(Base):
    """行星 = 知识点。每颗行星属于一个星系。"""

    __tablename__ = "planets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    galaxy_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    difficulty: Mapped[str] = mapped_column(String(16), nullable=False, default="medium", comment="easy/medium/hard")
    orbit_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="所在轨道层")
    angle_deg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="轨道初始角度")
    radius_offset: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="轨道半径微调")
    prerequisites: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="前置行星 slug 列表")
    question_tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list, comment="出题标签")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
