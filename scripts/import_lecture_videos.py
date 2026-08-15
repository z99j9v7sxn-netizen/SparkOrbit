"""扫描 资料/考研讲义视频/ 下 MP4 并幂等写入星库（video_local）。

支持目录结构（任选）：
  资料/考研讲义视频/计算机网络/01.第一章 .../*.mp4   ← 中文科目 + 章节子目录
  资料/考研讲义视频/computer-network/osi.mp4      ← 英文 galaxy_slug 扁平
  资料/考研讲义视频/*.mp4                        ← 无科目目录

- 文件不拷贝：file_url 指向 /static/materials/...
- 去重键：meta_json.source_path
- asset_type = video_local，出现在「考研讲义 → 视频观看」

用法（项目根）:
  .\\.venv\\Scripts\\python.exe scripts\\import_lecture_videos.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.core.paths import MATERIALS_DIR  # noqa: E402
from app.db.session import AsyncSessionLocal, init_db  # noqa: E402
from app.models.star_asset import StarAsset  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.seed_content import seed_content  # noqa: E402
from app.services.starlib import create_local_video_asset  # noqa: E402

LECTURE_VIDEO_ROOT = MATERIALS_DIR / "考研讲义视频"

# 中文科目名 / 英文 slug → 星系 slug
GALAXY_ALIASES: dict[str, str] = {
    "数据结构": "data-structure",
    "数据结构与算法": "data-structure",
    "data-structure": "data-structure",
    "操作系统": "operating-system",
    "operating-system": "operating-system",
    "计算机网络": "computer-network",
    "computer-network": "computer-network",
    "计算机组成原理": "computer-organization",
    "computer-organization": "computer-organization",
}


def materials_file_url(rel: str) -> str:
    parts = Path(rel).as_posix().split("/")
    encoded = "/".join(quote(p, safe="") for p in parts)
    return f"/static/materials/{encoded}"


def _source_path_key(rel: str) -> str:
    return Path(rel).as_posix()


def _resolve_galaxy_slug(folder_name: str) -> str:
    key = folder_name.strip()
    if key in GALAXY_ALIASES:
        return GALAXY_ALIASES[key]
    # 容错：去掉「星系」后缀
    for alias, slug in GALAXY_ALIASES.items():
        if key.startswith(alias):
            return slug
    return key


async def _find_owner(session) -> User:
    for uname in ("teacher001", "admin", "teacher"):
        row = (await session.execute(select(User).where(User.username == uname))).scalar_one_or_none()
        if row:
            return row
    row = (await session.execute(select(User).where(User.role == "teacher").limit(1))).scalar_one_or_none()
    if row:
        return row
    raise RuntimeError("未找到教师账号，请先启动后端完成 seed_demo_users")


def _title_from_stem(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").strip() or stem


def _chapter_label(mp4: Path, subject_dir: Path) -> str:
    """章节子目录名；若 MP4 直接在科目目录下则返回空。"""
    try:
        rel = mp4.parent.relative_to(subject_dir)
    except ValueError:
        return ""
    if str(rel) in (".", ""):
        return ""
    # 多级时用相对路径；通常一层章节
    return rel.as_posix().replace("/", " · ")


def _build_title(mp4: Path, subject_dir: Path | None) -> str:
    stem = _title_from_stem(mp4.stem)
    if subject_dir is None:
        return f"{stem} · 考研讲义"
    chapter = _chapter_label(mp4, subject_dir)
    if chapter:
        return f"{chapter} · {stem}"
    return f"{stem} · 考研讲义"


def _folder_meta(mp4: Path, subject_dir: Path | None) -> dict[str, str]:
    """从磁盘路径提取科目/章节，供前端按目录树展示。"""
    if subject_dir is None:
        return {"subject": "", "chapter": "", "file_stem": _title_from_stem(mp4.stem)}
    subject = subject_dir.name.strip()
    chapter = _chapter_label(mp4, subject_dir)
    return {
        "subject": subject,
        "chapter": chapter,
        "file_stem": _title_from_stem(mp4.stem),
    }


def _lecture_meta_json(source_path: str, folder: dict[str, str]) -> dict:
    return {
        "mode": "kaoyan",
        "source": "materials_lecture_video",
        "source_path": source_path,
        "category": "kaoyan_lecture_video",
        "subject": folder.get("subject") or "",
        "chapter": folder.get("chapter") or "",
        "file_stem": folder.get("file_stem") or "",
    }


async def _sync_existing_meta(
    session,
    row: StarAsset,
    *,
    title: str,
    galaxy_slug: str,
    meta: dict,
) -> bool:
    """已导入记录：补齐/纠正目录元数据与标题，便于分目录展示。"""
    cur = row.meta_json if isinstance(row.meta_json, dict) else {}
    need = False
    for k in ("subject", "chapter", "file_stem", "source_path", "category"):
        if cur.get(k) != meta.get(k):
            need = True
            break
    if row.title != title or (galaxy_slug and row.galaxy_slug != galaxy_slug):
        need = True
    if not need:
        return False
    merged = {**cur, **meta}
    row.meta_json = merged
    row.title = title
    if galaxy_slug:
        row.galaxy_slug = galaxy_slug
    await session.commit()
    return True


async def _import_one(
    session,
    owner: User,
    existing: list[StarAsset],
    *,
    rel: str,
    title: str,
    galaxy_slug: str,
    folder: dict[str, str],
) -> tuple[str, list[StarAsset]]:
    """返回 (status, updated_existing)。status: ok|skip|fail|sync"""
    source_path = _source_path_key(rel)
    meta = _lecture_meta_json(source_path, folder)
    for r in existing:
        m = r.meta_json if isinstance(r.meta_json, dict) else {}
        if m.get("source_path") == source_path:
            if await _sync_existing_meta(session, r, title=title, galaxy_slug=galaxy_slug, meta=meta):
                print(f"SYNC  {source_path}")
                existing = (await session.execute(select(StarAsset))).scalars().all()
                return "sync", existing
            print(f"SKIP  {source_path}")
            return "skip", existing
    try:
        out = await create_local_video_asset(
            session,
            owner,
            title=title,
            file_url=materials_file_url(rel),
            galaxy_slug=galaxy_slug,
            planet_slug="",
            description="考研讲义 · 本地 MP4",
            meta_json=meta,
        )
        print(f"OK    {title} → {out.get('id')} ({galaxy_slug or '—'})")
        existing = (await session.execute(select(StarAsset))).scalars().all()
        return "ok", existing
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL  {source_path}: {exc}")
        return "fail", existing


async def main() -> int:
    if not LECTURE_VIDEO_ROOT.exists():
        LECTURE_VIDEO_ROOT.mkdir(parents=True, exist_ok=True)
        print(f"已创建空目录: {LECTURE_VIDEO_ROOT}")
        print("请将 MP4 放入 资料/考研讲义视频/<科目或galaxy_slug>/[章节]/ 后重新运行。")
        return 0

    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_content(session)
        owner = await _find_owner(session)
        existing = (await session.execute(select(StarAsset))).scalars().all()
        print(f"owner={owner.username} id={owner.id}")
        print(f"lecture_video_root={LECTURE_VIDEO_ROOT}")

        ok = skip = fail = sync = 0

        for galaxy_dir in sorted(LECTURE_VIDEO_ROOT.iterdir()):
            if not galaxy_dir.is_dir():
                continue
            if galaxy_dir.name.startswith("_"):
                continue
            galaxy_slug = _resolve_galaxy_slug(galaxy_dir.name)
            # 递归：仅导入 科目/章节/*.mp4；科目根下扁平 MP4（未分章节）跳过
            for mp4 in sorted(galaxy_dir.rglob("*.mp4")):
                if not mp4.is_file():
                    continue
                # 归档目录不导入
                if "_archived_unsectioned" in mp4.parts:
                    continue
                folder = _folder_meta(mp4, galaxy_dir)
                if not (folder.get("chapter") or "").strip():
                    print(f"SKIP  unsectioned {mp4.relative_to(MATERIALS_DIR).as_posix()}")
                    skip += 1
                    continue
                rel = mp4.relative_to(MATERIALS_DIR).as_posix()
                title = _build_title(mp4, galaxy_dir)
                status, existing = await _import_one(
                    session,
                    owner,
                    existing,
                    rel=rel,
                    title=title,
                    galaxy_slug=galaxy_slug,
                    folder=folder,
                )
                if status == "ok":
                    ok += 1
                elif status == "skip":
                    skip += 1
                elif status == "sync":
                    sync += 1
                else:
                    fail += 1

        # 直接放在 考研讲义视频/*.mp4（无科目子目录）→ 未分章节，跳过
        for mp4 in sorted(LECTURE_VIDEO_ROOT.glob("*.mp4")):
            if not mp4.is_file():
                continue
            print(f"SKIP  unsectioned {mp4.relative_to(MATERIALS_DIR).as_posix()}")
            skip += 1

        print(f"\nDone: imported={ok} synced={sync} skipped={skip} failed={fail}")
        return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
