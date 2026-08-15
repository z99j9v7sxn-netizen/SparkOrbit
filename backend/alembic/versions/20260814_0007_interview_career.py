"""模拟面试扩展：求职助手投递看板。

Revision ID: 20260814_0007
Revises: 20260814_0006
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260814_0007"
down_revision: Union[str, Sequence[str], None] = "20260814_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_TABLES = ("interview_applications",)


def upgrade() -> None:
    from app import models  # noqa: F401 — 注册全部表到 metadata
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES if name in Base.metadata.tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    from app import models  # noqa: F401
    from app.db.session import Base

    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in _NEW_TABLES if name in Base.metadata.tables]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
