"""学生业务 Agent 运行轨迹（管理端观测用）。"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    user_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    scene: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")
    # handoff | workflow | supervisor | council
    mode: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="workflow")
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="running")
    topic: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    # DAG / plan 快照，供前端按 mode 绘图
    graph_plan: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_agent: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentStep(Base):
    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    agent_role: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    parallel_group: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
