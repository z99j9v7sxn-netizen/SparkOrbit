from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True, "pool_timeout": 10}
if settings.database_url.startswith("mysql"):
    _engine_kwargs["connect_args"] = {"connect_timeout": 5}

engine = create_async_engine(settings.database_url, **_engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    import logging
    import subprocess
    import sys
    from pathlib import Path

    from app import models  # noqa: F401

    log = logging.getLogger("sparkorbit.db")
    backend_root = Path(__file__).resolve().parents[2]
    upgraded = False
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=str(backend_root),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode == 0:
            upgraded = True
            if proc.stdout:
                log.info("alembic upgrade head: %s", proc.stdout.strip()[:500])
        else:
            log.warning(
                "alembic upgrade failed (rc=%s): %s",
                proc.returncode,
                (proc.stderr or proc.stdout or "")[:800],
            )
    except Exception as exc:  # noqa: BLE001
        log.warning("alembic upgrade unavailable: %s", exc)

    async with engine.begin() as conn:
        if not upgraded:
            log.warning(
                "DEPRECATED: falling back to Base.metadata.create_all; "
                "prefer `cd backend && alembic upgrade head`"
            )
            await conn.run_sync(Base.metadata.create_all)
        for col, ddl in [
            ("avatar_cartoon_url", "VARCHAR(1024) NOT NULL DEFAULT ''"),
            ("avatar_model_url", "VARCHAR(1024) NOT NULL DEFAULT ''"),
            ("class_id", "VARCHAR(36) NOT NULL DEFAULT ''"),
            ("teacher_id", "VARCHAR(36) NOT NULL DEFAULT ''"),
            ("pet_slug", "VARCHAR(64) NOT NULL DEFAULT ''"),
            ("pet_affinity", "INTEGER NOT NULL DEFAULT 0"),
            ("equipped_title", "VARCHAR(128) NOT NULL DEFAULT ''"),
            ("study_theme", "VARCHAR(64) NOT NULL DEFAULT ''"),
            ("streak_days", "INTEGER NOT NULL DEFAULT 0"),
            ("mood", "VARCHAR(32) NOT NULL DEFAULT 'calm'"),
            ("is_active", "BOOLEAN NOT NULL DEFAULT 1"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        for col, ddl in [
            ("fragments", "JSON"),
            ("last_reviewed_at", "DATETIME"),
            ("decay_state", "VARCHAR(16) NOT NULL DEFAULT 'lit'"),
            ("is_permanent", "BOOLEAN NOT NULL DEFAULT 0"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE planet_mastery ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        try:
            await conn.execute(text("ALTER TABLE challenge_questions ADD COLUMN meta_json JSON"))
        except Exception:
            pass
        for col, ddl in [
            ("next_review_at", "DATETIME"),
            ("interval_index", "INTEGER NOT NULL DEFAULT 0"),
            ("review_count", "INTEGER NOT NULL DEFAULT 0"),
            ("last_result", "VARCHAR(16) NOT NULL DEFAULT ''"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE mistake_records ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        for col, ddl in [
            ("kind", "VARCHAR(16) NOT NULL DEFAULT 'standard'"),
            ("meta_json", "JSON"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE learning_paths ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        for col, ddl in [
            ("review_status", "VARCHAR(16) NOT NULL DEFAULT ''"),
            ("review_comment", "TEXT"),
            ("reviewed_by", "VARCHAR(36) NOT NULL DEFAULT ''"),
            ("reviewed_at", "DATETIME"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE generated_resources ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        for col, ddl in [
            ("reaction_summary", "TEXT NOT NULL"),
            ("image_url", "VARCHAR(1024) NOT NULL DEFAULT ''"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE tree_hole_posts ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        for col, ddl in [
            ("image_url", "VARCHAR(1024) NOT NULL DEFAULT ''"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE mood_diaries ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        for col, ddl in [
            ("missing_dimensions", "JSON"),
            ("follow_up_questions", "JSON"),
            ("user_id", "VARCHAR(36) NOT NULL DEFAULT ''"),
            ("dimension_floors_json", "JSON"),
            ("warnings_json", "JSON"),
            ("raw_evidence", "JSON"),
            ("modality_preference", "JSON"),
            ("motivation_level", "JSON"),
        ]:
            try:
                await conn.execute(text(f"ALTER TABLE student_profiles ADD COLUMN {col} {ddl}"))
            except Exception:
                pass
        # 旧库 raw_evidence 为 NOT NULL 且无默认值，补默认以免 INSERT 失败
        try:
            await conn.execute(
                text(
                    "ALTER TABLE student_profiles MODIFY COLUMN raw_evidence JSON NULL "
                    "DEFAULT (JSON_OBJECT())"
                )
            )
        except Exception:
            try:
                await conn.execute(
                    text("ALTER TABLE student_profiles ALTER COLUMN raw_evidence SET DEFAULT (JSON_OBJECT())")
                )
            except Exception:
                pass

        # learning_paths: 旧仿真表结构与 PathPlanner ORM 不一致时备份并重建
        try:
            cols = (
                await conn.execute(
                    text(
                        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'learning_paths'"
                    )
                )
            ).fetchall()
            col_names = {row[0] for row in cols}
            if col_names and "title" not in col_names:
                await conn.execute(text("RENAME TABLE learning_paths TO learning_paths_legacy"))
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            # SQLite 或其他方言：尝试检测并重建
            try:
                await conn.execute(text("SELECT title FROM learning_paths LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(text("ALTER TABLE learning_paths RENAME TO learning_paths_legacy"))
                except Exception:
                    try:
                        await conn.execute(text("DROP TABLE IF EXISTS learning_paths"))
                    except Exception:
                        pass
                await conn.run_sync(Base.metadata.create_all)

        # profile_extractions: 旧表无 student_name/summary/source，与 ORM 不一致时备份并重建
        try:
            cols = (
                await conn.execute(
                    text(
                        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'profile_extractions'"
                    )
                )
            ).fetchall()
            col_names = {row[0] for row in cols}
            if col_names and "student_name" not in col_names:
                await conn.execute(text("RENAME TABLE profile_extractions TO profile_extractions_legacy"))
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            try:
                await conn.execute(text("SELECT student_name FROM profile_extractions LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(
                        text("ALTER TABLE profile_extractions RENAME TO profile_extractions_legacy")
                    )
                except Exception:
                    try:
                        await conn.execute(text("DROP TABLE IF EXISTS profile_extractions"))
                    except Exception:
                        pass
                await conn.run_sync(Base.metadata.create_all)

        # simulation_runs: 旧表用 student_profile_id、无 profile_id/mode，与 ORM 不一致时备份重建
        try:
            cols = (
                await conn.execute(
                    text(
                        "SELECT COLUMN_NAME FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'simulation_runs'"
                    )
                )
            ).fetchall()
            col_names = {row[0] for row in cols}
            if col_names and "profile_id" not in col_names:
                await conn.execute(text("RENAME TABLE simulation_runs TO simulation_runs_legacy"))
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            try:
                await conn.execute(text("SELECT profile_id FROM simulation_runs LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(text("ALTER TABLE simulation_runs RENAME TO simulation_runs_legacy"))
                except Exception:
                    try:
                        await conn.execute(text("DROP TABLE IF EXISTS simulation_runs"))
                    except Exception:
                        pass
                await conn.run_sync(Base.metadata.create_all)

        # simulation_events: payload 非 JSON 时备份重建以对齐 ORM
        try:
            cols = (
                await conn.execute(
                    text(
                        "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
                        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'simulation_events'"
                    )
                )
            ).fetchall()
            col_map = {row[0]: (row[1] or "").lower() for row in cols}
            if col_map and (
                "payload" not in col_map or col_map.get("payload") in {"text", "longtext", "mediumtext", "varchar"}
            ):
                await conn.execute(text("RENAME TABLE simulation_events TO simulation_events_legacy"))
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            try:
                await conn.execute(text("SELECT payload FROM simulation_events LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(
                        text("ALTER TABLE simulation_events RENAME TO simulation_events_legacy")
                    )
                except Exception:
                    try:
                        await conn.execute(text("DROP TABLE IF EXISTS simulation_events"))
                    except Exception:
                        pass
                await conn.run_sync(Base.metadata.create_all)

        # planet_mastery: 多闸门字段
        for col, ddl in (
            ("mastery_phase", "ALTER TABLE planet_mastery ADD COLUMN mastery_phase VARCHAR(24) NOT NULL DEFAULT 'dim'"),
            ("gate_flags", "ALTER TABLE planet_mastery ADD COLUMN gate_flags JSON"),
            ("learn_evidence", "ALTER TABLE planet_mastery ADD COLUMN learn_evidence JSON"),
        ):
            try:
                await conn.execute(text(f"SELECT {col} FROM planet_mastery LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass

        # notes: 卡片块与来源 / 星系层级
        for col, ddl in (
            ("blocks_json", "ALTER TABLE notes ADD COLUMN blocks_json JSON"),
            ("source", "ALTER TABLE notes ADD COLUMN source VARCHAR(64) NOT NULL DEFAULT 'manual'"),
            ("session_id", "ALTER TABLE notes ADD COLUMN session_id VARCHAR(64) NOT NULL DEFAULT ''"),
            ("galaxy_slug", "ALTER TABLE notes ADD COLUMN galaxy_slug VARCHAR(128) NOT NULL DEFAULT ''"),
        ):
            try:
                await conn.execute(text(f"SELECT {col} FROM notes LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass

        # 资料站来源追溯 + 画像更新来源
        for table, col, ddl in (
            ("resource_forum_posts", "source_type", "ALTER TABLE resource_forum_posts ADD COLUMN source_type VARCHAR(32) NOT NULL DEFAULT ''"),
            ("resource_forum_posts", "source_id", "ALTER TABLE resource_forum_posts ADD COLUMN source_id VARCHAR(512) NOT NULL DEFAULT ''"),
            ("student_profiles", "update_source", "ALTER TABLE student_profiles ADD COLUMN update_source VARCHAR(32) NOT NULL DEFAULT 'profiler'"),
        ):
            try:
                await conn.execute(text(f"SELECT {col} FROM {table} LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass

        # lesson_resources: 教师知识库分类 + 升格星库
        for col, ddl in (
            (
                "resource_kind",
                "ALTER TABLE lesson_resources ADD COLUMN resource_kind VARCHAR(32) NOT NULL DEFAULT 'other'",
            ),
            (
                "promoted_asset_id",
                "ALTER TABLE lesson_resources ADD COLUMN promoted_asset_id VARCHAR(36) NOT NULL DEFAULT ''",
            ),
        ):
            try:
                await conn.execute(text(f"SELECT {col} FROM lesson_resources LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass

        # assignments: AI 提取题目 + 知识库来源
        for col, ddl in (
            ("questions_json", "ALTER TABLE assignments ADD COLUMN questions_json JSON"),
            (
                "source_resource_id",
                "ALTER TABLE assignments ADD COLUMN source_resource_id VARCHAR(36) NOT NULL DEFAULT ''",
            ),
        ):
            try:
                await conn.execute(text(f"SELECT {col} FROM assignments LIMIT 1"))
            except Exception:
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass
