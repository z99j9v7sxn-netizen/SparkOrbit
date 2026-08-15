"""管理端安全运营模型：操作审计 / 登录日志 / 系统告警 / 安全日报 / 反馈工单 / 运行时配置。"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuditLog(Base):
    """管理员敏感操作审计（用户启停、删除内容、维护开关等）。"""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    username: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class LoginLog(Base):
    """登录成功 / 失败日志（安全审计与异常登录告警数据源）。"""

    __tablename__ = "login_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    username: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    ip: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    user_agent: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class SystemAlert(Base):
    """系统级告警（区别于教学侧 alerts 表），带研判处置闭环。"""

    __tablename__ = "system_alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    # info | warning | critical
    level: Mapped[str] = mapped_column(String(16), index=True, nullable=False, default="info")
    # llm_failure | token_quota | agent_failure | login_security | manual
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False, default="")
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    detail: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # open | acked | resolved | false_positive
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="open")
    # AI 研判结论：true_positive | false_positive | uncertain
    triage_verdict: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    triage_note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SecurityReport(Base):
    """每日安全运营日报（规则汇聚 + LLM 摘要）。"""

    __tablename__ = "security_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    report_date: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    markdown_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # rule | llm
    generated_by: Mapped[str] = mapped_column(String(16), nullable=False, default="rule")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    """用户反馈工单（bug / 建议 / 内容纠错）。"""

    __tablename__ = "feedbacks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False, default="")
    user_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="student")
    # bug | suggestion | content
    category: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="suggestion")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # open | processing | closed
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="open")
    reply: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SettingEntry(Base):
    """运行时 key-value 配置（配额 / 防火墙 / 功能开关 / 定时任务心跳）。"""

    __tablename__ = "setting_entries"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
