"""模拟面试扩展：练习记录表 + prep_intel / prosody_detail 列。

Revision ID: 20260814_0006
Revises: 20260813_0005
Create Date: 2026-08-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260814_0006"
down_revision: Union[str, Sequence[str], None] = "20260813_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("interview_practice_records",)


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    from app import models  # noqa: F401 — 注册全部表到 metadata
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES if name in Base.metadata.tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)

    # MySQL 不允许 JSON 列带 server default，列设为可空、由 ORM 默认 dict 填充
    if not _has_column("interview_sessions", "prep_intel"):
        op.add_column("interview_sessions", sa.Column("prep_intel", sa.JSON(), nullable=True))
    if not _has_column("interview_turns", "prosody_detail"):
        op.add_column("interview_turns", sa.Column("prosody_detail", sa.JSON(), nullable=True))


def downgrade() -> None:
    from app import models  # noqa: F401
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES if name in Base.metadata.tables]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)

    if _has_column("interview_turns", "prosody_detail"):
        op.drop_column("interview_turns", "prosody_detail")
    if _has_column("interview_sessions", "prep_intel"):
        op.drop_column("interview_sessions", "prep_intel")
