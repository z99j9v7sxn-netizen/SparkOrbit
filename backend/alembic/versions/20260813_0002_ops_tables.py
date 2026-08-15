"""ops: 管理端安全运营新表（审计/登录日志/系统告警/安全日报/反馈/运行时配置）。

Revision ID: 20260813_0002
Revises: 20260812_0001
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260813_0002"
down_revision: Union[str, Sequence[str], None] = "20260812_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "audit_logs",
    "login_logs",
    "system_alerts",
    "security_reports",
    "feedbacks",
    "setting_entries",
)


def upgrade() -> None:
    from app import models  # noqa: F401 — 注册全部表到 metadata
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _TABLES if name in Base.metadata.tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    from app import models  # noqa: F401
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _TABLES if name in Base.metadata.tables]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
