"""将 资料/ 下课本与考研复习指导书批量写入星库（幂等）。

- 文件不拷贝：file_url 指向 /static/materials/...
- 去重键：meta_json.source_path
- 抽页上限与 starlib.extract_pdf_pages 一致（默认 200 页）→ RAG

用法（项目根）:
  .\\.venv\\Scripts\\python.exe scripts\\import_materials_to_starlib.py
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
from app.services.starlib import create_pdf_asset  # noqa: E402

# 相对 资料/ 的显式清单：(相对路径, 标题, asset_type, galaxy_slug, description)
MATERIAL_CATALOG: list[tuple[str, str, str, str, str]] = [
    # 课本
    ("课本/严蔚敏 数据结构  C语言版.pdf", "严蔚敏 数据结构（C语言版）", "book", "data-structure", "原书 · 严蔚敏"),
    ("课本/计算机网络（第8版） (谢希仁) .pdf", "计算机网络（第8版）谢希仁", "book", "computer-network", "原书 · 谢希仁"),
    ("课本/计算机组成原理 第3版 (唐朔飞) .pdf", "计算机组成原理（第3版）唐朔飞", "book", "computer-organization", "原书 · 唐朔飞"),
    ("课本/计算机组成与系统结构-第3版-袁春风.pdf", "计算机组成与系统结构（第3版）袁春风", "book", "computer-organization", "原书 · 袁春风"),
    ("课本/高等数学第8版上册.pdf", "高等数学（第8版）上册", "book", "higher-math", "原书 · 同济高数"),
    ("课本/高等数学第8版下册.pdf", "高等数学（第8版）下册", "book", "higher-math", "原书 · 同济高数"),
    ("课本/工程数学 线性代数 第七版 同济大学.pdf", "工程数学 线性代数（第七版）同济", "book", "higher-math", "原书 · 线性代数"),
    ("课本/概率论与数理统计 第五版.pdf", "概率论与数理统计（第五版）", "book", "higher-math", "原书 · 概率统计"),
    # 考研复习指导书（王道）— meta.category=kaoyan_guide，前端归入「考研讲义 → 书本阅读」
    ("考研复习指导书/2027数据结构_高清带书签版.pdf", "王道 2027 数据结构", "book", "data-structure", "考研复习指导 · 王道"),
    ("考研复习指导书/2027计算机网络_高清带书签版.pdf", "王道 2027 计算机网络", "book", "computer-network", "考研复习指导 · 王道"),
    ("考研复习指导书/王道2027操作系统-高清带书签.pdf", "王道 2027 操作系统", "book", "operating-system", "考研复习指导 · 王道"),
    ("考研复习指导书/2027计算机组成原理_高清带书签版.pdf", "王道 2027 计算机组成原理", "book", "computer-organization", "考研复习指导 · 王道"),
    # 根目录补充
    ("数据结构(c语言版)复习知识点.pdf", "数据结构复习知识点", "pdf", "data-structure", "复习提纲"),
    ("数据结构题集 严蔚敏 C语言版.pdf", "数据结构题集 严蔚敏 C语言版", "problem_doc", "data-structure", "题集 · 严蔚敏"),
]


def materials_file_url(rel: str) -> str:
    """生成可被 StaticFiles 解析的 URL（路径段百分号编码）。"""
    parts = Path(rel).as_posix().split("/")
    encoded = "/".join(quote(p, safe="") for p in parts)
    return f"/static/materials/{encoded}"


def _source_path_key(rel: str) -> str:
    return Path(rel).as_posix()


async def _find_owner(session) -> User:
    for uname in ("teacher001", "admin", "teacher"):
        row = (await session.execute(select(User).where(User.username == uname))).scalar_one_or_none()
        if row:
            return row
    row = (await session.execute(select(User).where(User.role == "teacher").limit(1))).scalar_one_or_none()
    if row:
        return row
    raise RuntimeError("未找到教师账号，请先启动后端完成 seed_demo_users")


def _already_imported(rows: list[StarAsset], source_path: str) -> bool:
    for r in rows:
        meta = r.meta_json if isinstance(r.meta_json, dict) else {}
        if meta.get("source_path") == source_path:
            return True
    return False


async def main() -> int:
    if not MATERIALS_DIR.exists():
        print(f"FAIL: 资料目录不存在: {MATERIALS_DIR}")
        return 1

    await init_db()
    async with AsyncSessionLocal() as session:
        await seed_content(session)
        owner = await _find_owner(session)
        existing = (await session.execute(select(StarAsset))).scalars().all()
        print(f"owner={owner.username} id={owner.id}")
        print(f"materials_dir={MATERIALS_DIR}")
        print(f"existing_star_assets={len(existing)}")

        ok = skip = fail = 0
        for rel, title, asset_type, galaxy_slug, description in MATERIAL_CATALOG:
            source_path = _source_path_key(rel)
            path = MATERIALS_DIR / Path(rel)
            if not path.is_file():
                print(f"MISS  {source_path}")
                fail += 1
                continue
            if _already_imported(existing, source_path):
                print(f"SKIP  {title} ({source_path})")
                skip += 1
                continue

            print(f"INGEST {title} … ({path.stat().st_size / 1e6:.1f} MB)")
            try:
                pdf_bytes = path.read_bytes()
                out = await create_pdf_asset(
                    session,
                    owner,
                    title=title,
                    file_url=materials_file_url(rel),
                    pdf_bytes=pdf_bytes,
                    galaxy_slug=galaxy_slug,
                    asset_type=asset_type,
                    description=description,
                    extra_meta={
                        "source_path": source_path,
                        "import": "materials_batch",
                        "category": "kaoyan_guide" if "考研复习指导书" in source_path else "textbook",
                    },
                )
                print(
                    f"  OK  status={out.get('status')} pages={out.get('page_count')} "
                    f"chunks={out.get('chunk_count')} galaxy={galaxy_slug} id={out.get('id')}"
                )
                ok += 1
                # refresh existing list for subsequent de-dupe in same run
                existing = (await session.execute(select(StarAsset))).scalars().all()
            except Exception as exc:
                print(f"  FAIL {title}: {exc}")
                fail += 1

        print(f"\nDone: imported={ok} skipped={skip} failed={fail}")
        return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
