"""baseline: 用 ORM metadata 建全量表结构（开发空库可 upgrade；已有库 stamp 后增量）。

Revision ID: 20260812_0001
Revises:
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260812_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app import models  # noqa: F401 — 注册全部表到 metadata
    from app.db.session import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app import models  # noqa: F401
    from app.db.session import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
