"""teacher suite: 题库/私信/分组/激励/日历新表 + generated_resources 审核列。

Revision ID: 20260813_0003
Revises: 20260813_0002
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260813_0003"
down_revision: Union[str, Sequence[str], None] = "20260813_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "question_bank_items",
    "direct_messages",
    "student_groups",
    "praise_records",
    "teacher_calendar_events",
)

_GEN_RES_COLUMNS = (
    ("review_status", "VARCHAR(16) NOT NULL DEFAULT ''"),
    ("review_comment", "TEXT"),
    ("reviewed_by", "VARCHAR(36) NOT NULL DEFAULT ''"),
    ("reviewed_at", "DATETIME"),
)


def upgrade() -> None:
    from app import models  # noqa: F401 — 注册全部表到 metadata
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _TABLES if name in Base.metadata.tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)

    for col, ddl in _GEN_RES_COLUMNS:
        try:
            op.execute(f"ALTER TABLE generated_resources ADD COLUMN {col} {ddl}")
        except Exception:  # noqa: BLE001 — 列已存在时忽略
            pass


def downgrade() -> None:
    from app import models  # noqa: F401
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _TABLES if name in Base.metadata.tables]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
