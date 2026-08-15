from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StudyRoom(Base):
    """自习室：黄道十二宫下的「星」节点，分大小自习室并有人数上限。"""

    __tablename__ = "study_rooms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    constellation: Mapped[str] = mapped_column(String(32), index=True, comment="星座 slug")
    name: Mapped[str] = mapped_column(String(128))
    size: Mapped[str] = mapped_column(String(16), comment="large | small")
    capacity: Mapped[int] = mapped_column(Integer, default=6)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
