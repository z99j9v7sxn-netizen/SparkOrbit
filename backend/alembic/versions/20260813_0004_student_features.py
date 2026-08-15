"""学生端新功能：SRS 复习卡 / 考级中心（题库、试卷、模考、词书、打卡挑战）+ mistake_records SRS 列。

Revision ID: 20260813_0004
Revises: 20260813_0003
Create Date: 2026-08-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260813_0004"
down_revision: Union[str, Sequence[str], None] = "20260813_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = (
    "review_cards",
    "exam_questions",
    "exam_papers",
    "exam_mock_runs",
    "exam_practice_logs",
    "exam_word_entries",
    "challenge_campaigns",
)

_MISTAKE_COLUMNS = (
    ("next_review_at", "DATETIME"),
    ("interval_index", "INTEGER NOT NULL DEFAULT 0"),
    ("review_count", "INTEGER NOT NULL DEFAULT 0"),
    ("last_result", "VARCHAR(16) NOT NULL DEFAULT ''"),
)

_PATH_COLUMNS = (
    ("kind", "VARCHAR(16) NOT NULL DEFAULT 'standard'"),
    ("meta_json", "JSON"),
)


def upgrade() -> None:
    from app import models  # noqa: F401 — 注册全部表到 metadata
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _TABLES if name in Base.metadata.tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)

    for col, ddl in _MISTAKE_COLUMNS:
        try:
            op.execute(f"ALTER TABLE mistake_records ADD COLUMN {col} {ddl}")
        except Exception:  # noqa: BLE001 — 列已存在时忽略
            pass

    for col, ddl in _PATH_COLUMNS:
        try:
            op.execute(f"ALTER TABLE learning_paths ADD COLUMN {col} {ddl}")
        except Exception:  # noqa: BLE001 — 列已存在时忽略
            pass


def downgrade() -> None:
    from app import models  # noqa: F401
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _TABLES if name in Base.metadata.tables]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
