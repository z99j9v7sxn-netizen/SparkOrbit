"""模拟面试区：interview_sessions / interview_turns / interview_reports。

Revision ID: 20260813_0005
Revises: 20260813_0004
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260813_0005"
down_revision: Union[str, Sequence[str], None] = "20260813_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "interview_sessions",
    "interview_turns",
    "interview_reports",
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
