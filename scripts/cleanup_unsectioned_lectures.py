"""删除星库中「未分章节」的本地讲义视频，并移走对应磁盘文件以免再次导入。

识别：asset_type=video_local 且 meta_json.chapter 为空（含缺失）。
对 meta.source=materials_lecture_video 的文件：移到
  资料/考研讲义视频/_archived_unsectioned/
种子 static_media 未分章节条目仅删库记录，不删 /static/media 文件。

用法（项目根）:
  .\\.venv\\Scripts\\python.exe scripts\\cleanup_unsectioned_lectures.py
  .\\.venv\\Scripts\\python.exe scripts\\cleanup_unsectioned_lectures.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.core.paths import MATERIALS_DIR  # noqa: E402
from app.db.session import AsyncSessionLocal, init_db  # noqa: E402
from app.models.star_asset import StarAsset  # noqa: E402

ARCHIVE_DIR = MATERIALS_DIR / "考研讲义视频" / "_archived_unsectioned"


def _chapter_empty(meta: dict) -> bool:
    ch = meta.get("chapter")
    return ch is None or str(ch).strip() == ""


def _archive_materials_file(source_path: str, dry_run: bool) -> str:
    """返回动作说明。"""
    if not source_path:
        return "no-source-path"
    src = MATERIALS_DIR / Path(source_path)
    if not src.is_file():
        return f"missing-file:{source_path}"
    dest = ARCHIVE_DIR / Path(source_path).name
    # 避免重名覆盖：加父目录前缀
    parent_name = Path(source_path).parent.name
    if parent_name and parent_name != "考研讲义视频":
        dest = ARCHIVE_DIR / f"{parent_name}__{Path(source_path).name}"
    if dry_run:
        return f"would-archive:{src} -> {dest}"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    return f"archived:{dest}"


async def run(*, dry_run: bool) -> int:
    await init_db()
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(select(StarAsset).where(StarAsset.asset_type == "video_local"))
        ).scalars().all()
        targets = []
        for r in rows:
            meta = r.meta_json if isinstance(r.meta_json, dict) else {}
            if not _chapter_empty(meta):
                continue
            source = str(meta.get("source") or "")
            file_url = (r.file_url or "").strip()
            # 仅清用户导入/上传的未分章节；保留 static_media 演示种子
            if source == "static_media":
                continue
            if source == "materials_lecture_video" or file_url.startswith("/static/uploads/starlib/"):
                targets.append(r)
            elif source in ("", "None") and meta.get("mode") == "kaoyan" and not file_url.startswith("/static/media/"):
                targets.append(r)

        print(f"found_unsectioned={len(targets)} dry_run={dry_run}")
        for r in targets:
            meta = r.meta_json if isinstance(r.meta_json, dict) else {}
            source = str(meta.get("source") or "")
            source_path = str(meta.get("source_path") or "")
            action = "db-only"
            if source == "materials_lecture_video":
                action = _archive_materials_file(source_path, dry_run=dry_run)
            print(f"DEL  id={r.id} title={r.title!r} source={source or '-'} {action}")
            if not dry_run:
                await session.delete(r)

        if not dry_run and targets:
            await session.commit()
        print(f"Done: deleted={0 if dry_run else len(targets)} (dry_run kept={len(targets) if dry_run else 0})")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="清理未分章节讲义视频")
    parser.add_argument("--dry-run", action="store_true", help="只打印不删除")
    args = parser.parse_args()
    return asyncio.run(run(dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
