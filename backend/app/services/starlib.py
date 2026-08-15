"""星库服务：上传、列表、分页入库 RAG、阅读进度证据。"""
from __future__ import annotations

import io
import re
import uuid
from typing import Any
from urllib.parse import unquote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import STARLIB_DIR
from app.models.galaxy import Planet
from app.models.school_class import SchoolClass
from app.models.star_asset import StarAsset
from app.models.user import User
from app.services import mastery_gates as gates
from app.services.rag import ingest_pages

try:
    from pypdf import PdfReader  # type: ignore

    _PDF_OK = True
except ImportError:
    PdfReader = None  # type: ignore
    _PDF_OK = False


def _bvid_from_url(text: str) -> str:
    t = (text or "").strip()
    m = re.search(r"(BV[\w]+)", t, re.I)
    return m.group(1) if m else t


def extract_pdf_pages(data: bytes, max_pages: int = 200) -> list[dict[str, Any]]:
    if not _PDF_OK or not data:
        return []
    reader = PdfReader(io.BytesIO(data))
    pages: list[dict[str, Any]] = []
    for i, page in enumerate(reader.pages[:max_pages]):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": i + 1, "text": text})
    return pages


def _row_out(row: StarAsset) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "asset_type": row.asset_type,
        "galaxy_slug": row.galaxy_slug,
        "planet_slug": row.planet_slug,
        "file_url": row.file_url,
        "bilibili_bvid": row.bilibili_bvid,
        "description": row.description,
        "page_count": row.page_count,
        "chunk_count": row.chunk_count,
        "status": row.status,
        "owner_id": row.owner_id,
        "class_id": row.class_id,
        "meta_json": row.meta_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def resolve_upload_class_id(user: User, class_id: str = "") -> str:
    """学生强制本班；教师可用传入 class_id，否则用自身 class_id。"""
    role = (user.role or "").strip()
    if role == "student":
        cid = (user.class_id or "").strip()
        if not cid:
            raise ValueError("学生需先加入班级才能上传到星库")
        return cid
    return (class_id or user.class_id or "").strip()


async def _teacher_class_ids(session: AsyncSession, user: User) -> set[str]:
    rows = (
        await session.execute(select(SchoolClass.id).where(SchoolClass.teacher_id == user.id))
    ).scalars().all()
    return {str(x) for x in rows}


async def can_delete_asset(session: AsyncSession, user: User, row: StarAsset) -> bool:
    role = (user.role or "").strip()
    if role == "admin":
        return True
    if row.owner_id == user.id:
        return True
    if role == "student":
        return False
    if role == "teacher":
        cid = (row.class_id or "").strip()
        if not cid:
            # 全局/校本讲义：教师可清理
            return True
        return cid in await _teacher_class_ids(session, user)
    return False


def _unlink_starlib_upload(file_url: str) -> None:
    """仅删除 uploads/starlib 下的本地上传文件；materials 静态资料不动。"""
    url = (file_url or "").strip()
    prefix = "/static/uploads/starlib/"
    if not url.startswith(prefix):
        return
    name = unquote(url[len(prefix) :].split("?", 1)[0].strip("/"))
    if not name or ".." in name or "/" in name or "\\" in name:
        return
    path = STARLIB_DIR / name
    try:
        if path.is_file() and path.resolve().is_relative_to(STARLIB_DIR.resolve()):
            path.unlink(missing_ok=True)
    except OSError:
        pass


async def delete_asset(session: AsyncSession, user: User, asset_id: str) -> dict:
    row = (await session.execute(select(StarAsset).where(StarAsset.id == asset_id))).scalar_one_or_none()
    if row is None:
        raise LookupError("资产不存在")
    if not await can_delete_asset(session, user, row):
        raise PermissionError("无权删除该星库资产")
    file_url = row.file_url or ""
    await session.delete(row)
    await session.commit()
    _unlink_starlib_upload(file_url)
    return {"ok": True, "id": asset_id}


async def list_assets(
    session: AsyncSession,
    user: User,
    *,
    galaxy_slug: str = "",
    asset_type: str = "",
) -> list[dict]:
    stmt = select(StarAsset).order_by(StarAsset.created_at.desc())
    if galaxy_slug:
        stmt = stmt.where(StarAsset.galaxy_slug == galaxy_slug)
    if asset_type:
        stmt = stmt.where(StarAsset.asset_type == asset_type)
    if user.role == "student" and user.class_id:
        stmt = stmt.where((StarAsset.class_id == user.class_id) | (StarAsset.class_id == "") | (StarAsset.class_id.is_(None)))
    # 考研讲义视频按科目/章节入库后数量可超过 200
    rows = (await session.execute(stmt.limit(2000))).scalars().all()
    return [_row_out(r) for r in rows]


async def get_asset(session: AsyncSession, asset_id: str) -> dict | None:
    row = (await session.execute(select(StarAsset).where(StarAsset.id == asset_id))).scalar_one_or_none()
    return _row_out(row) if row else None


async def create_bilibili_asset(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    bvid_or_url: str,
    galaxy_slug: str = "",
    planet_slug: str = "",
    description: str = "",
    class_id: str = "",
) -> dict:
    resolved_class = resolve_upload_class_id(user, class_id)
    bvid = _bvid_from_url(bvid_or_url)
    row = StarAsset(
        id=str(uuid.uuid4()),
        title=title.strip() or f"B站 {bvid}",
        asset_type="video_bilibili",
        galaxy_slug=galaxy_slug.strip(),
        planet_slug=planet_slug.strip(),
        bilibili_bvid=bvid,
        description=description.strip(),
        status="ready",
        owner_id=user.id,
        class_id=resolved_class,
        meta_json={"embed": f"https://www.bilibili.com/video/{bvid}"},
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_out(row)


async def create_pdf_asset(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    file_url: str,
    pdf_bytes: bytes,
    galaxy_slug: str = "",
    planet_slug: str = "",
    asset_type: str = "pdf",
    description: str = "",
    extra_meta: dict | None = None,
    class_id: str = "",
) -> dict:
    resolved_class = resolve_upload_class_id(user, class_id)
    row = StarAsset(
        id=str(uuid.uuid4()),
        title=title.strip() or "未命名教材",
        asset_type=asset_type if asset_type in ("book", "pdf", "problem_doc") else "pdf",
        galaxy_slug=galaxy_slug.strip(),
        planet_slug=planet_slug.strip(),
        file_url=file_url,
        description=description.strip(),
        status="parsing",
        owner_id=user.id,
        class_id=resolved_class,
    )
    session.add(row)
    await session.flush()

    pages = extract_pdf_pages(pdf_bytes)
    row.page_count = len(pages)
    chunks = 0
    if pages and galaxy_slug:
        chunks = ingest_pages(
            galaxy_slug=galaxy_slug,
            pages=pages,
            source=f"starlib:{row.id}",
            book_id=row.id,
            book_title=row.title,
            planet_slug=planet_slug,
        )
    row.chunk_count = chunks
    # 扫描版可能无文字层（pages=0），但仍可站内翻页阅读，故有 file_url 即 ready
    row.status = "ready" if (pages or file_url) else "failed"
    meta: dict[str, Any] = {"has_text": bool(pages)}
    if isinstance(extra_meta, dict):
        meta.update(extra_meta)
    row.meta_json = meta
    await session.commit()
    await session.refresh(row)
    return _row_out(row)


async def recommend_bilibili(topic: str, limit: int = 5) -> list[dict]:
    """基于主题生成推荐卡片（关键词级；无开放搜索密钥时用可演示列表）。

    前端在「原书模式」内嵌打开：优先用已知 BV，否则用搜索页 iframe。
    """
    topic = (topic or "数据结构").strip()
    # 部分主题给可嵌入的演示 BV（公开教学向），其余走搜索页站内打开
    known = {
        "osi": "BV1c4411d7jb",
        "tcp": "BV1iJ41117RH",
        "二叉树": "BV1uA411N7c5",
        "排序": "BV1x7411H77j",
    }
    bvid = ""
    low = topic.lower()
    for k, v in known.items():
        if k in low or k in topic:
            bvid = v
            break
    seeds = [
        {"title": f"{topic} 精讲入门", "reason": "适合建立直觉，贴合当前薄弱点", "suffix": "精讲"},
        {"title": f"{topic} 图解与例题", "reason": "可视化讲解，补练习前的概念缺口", "suffix": "图解"},
        {"title": f"{topic} 易错点梳理", "reason": "针对常见陷阱与对比辨析", "suffix": "易错"},
        {"title": f"{topic} 代码实现走读", "reason": "衔接演武舱与代码舱", "suffix": "代码"},
        {"title": f"{topic} 期末速通", "reason": "路径冲刺阶段可用", "suffix": "速通"},
    ]
    out = []
    for i, s in enumerate(seeds[:limit]):
        q = f"{topic} {s['suffix']}"
        out.append(
            {
                "title": s["title"],
                "bvid": bvid if i == 0 else "",
                "reason": s["reason"],
                "query": q,
                "search_url": f"https://search.bilibili.com/all?keyword={q}",
                "embed_url": (
                    f"https://player.bilibili.com/player.html?bvid={bvid}&high_quality=1"
                    if bvid and i == 0
                    else ""
                ),
                "open_in_app": True,
                "rank": i + 1,
            }
        )
    return out


# 考研讲义：映射仓库内已有本地 MP4（答辩可演示）
_LECTURE_SEEDS = [
    {
        "title": "OSI 七层模型 · 考研精讲",
        "file_url": "/static/media/osi-model.mp4",
        "planet_slug": "osi-model",
        "galaxy_slug": "computer-network",
        "description": "本地 MP4 讲义 · 考研模式",
    },
    {
        "title": "TCP 协议 · 考研精讲",
        "file_url": "/static/media/tcp-protocol.mp4",
        "planet_slug": "tcp-protocol",
        "galaxy_slug": "computer-network",
        "description": "本地 MP4 讲义 · 考研模式",
    },
    {
        "title": "进程与线程 · 考研精讲",
        "file_url": "/static/media/process-thread.mp4",
        "planet_slug": "process-thread",
        "galaxy_slug": "operating-system",
        "description": "本地 MP4 讲义 · 考研模式",
    },
    {
        "title": "二叉树 · 考研精讲（生成片）",
        "file_url": "/static/media/generated/binary-tree_83cceb85f1_cap.mp4",
        "planet_slug": "binary-tree",
        "galaxy_slug": "data-structure",
        "description": "字幕烧录版讲义视频",
    },
]


async def ensure_lecture_assets(session: AsyncSession, user: User, galaxy_slug: str = "") -> list[dict]:
    """确保考研讲义本地视频资产存在（幂等）。"""
    existing = (
        await session.execute(select(StarAsset).where(StarAsset.asset_type == "video_local"))
    ).scalars().all()
    by_url = {r.file_url: r for r in existing}
    created = False
    for seed in _LECTURE_SEEDS:
        if seed["file_url"] in by_url:
            continue
        if galaxy_slug and seed.get("galaxy_slug") and seed["galaxy_slug"] != galaxy_slug:
            # 仍创建全局讲义，便于跨星系演示
            pass
        row = StarAsset(
            id=str(uuid.uuid4()),
            title=seed["title"],
            asset_type="video_local",
            galaxy_slug=seed.get("galaxy_slug") or galaxy_slug or "",
            planet_slug=seed.get("planet_slug") or "",
            file_url=seed["file_url"],
            description=seed.get("description") or "",
            status="ready",
            owner_id=user.id,
            class_id=user.class_id or "",
            meta_json={"mode": "kaoyan", "source": "static_media"},
        )
        session.add(row)
        created = True
    if created:
        await session.commit()
    return await list_assets(session, user, galaxy_slug=galaxy_slug, asset_type="video_local")


async def create_local_video_asset(
    session: AsyncSession,
    user: User,
    *,
    title: str,
    file_url: str,
    galaxy_slug: str = "",
    planet_slug: str = "",
    description: str = "",
    meta_json: dict | None = None,
) -> dict:
    row = StarAsset(
        id=str(uuid.uuid4()),
        title=title.strip() or "本地讲义视频",
        asset_type="video_local",
        galaxy_slug=galaxy_slug.strip(),
        planet_slug=planet_slug.strip(),
        file_url=file_url,
        description=description.strip() or "考研讲义 · 本地 MP4",
        status="ready",
        owner_id=user.id,
        class_id=user.class_id or "",
        meta_json=meta_json if isinstance(meta_json, dict) else {"mode": "kaoyan"},
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_out(row)


async def mark_reading_progress(
    session: AsyncSession,
    user: User,
    *,
    asset_id: str,
    page: int = 1,
    seconds: int = 30,
) -> dict:
    asset = (await session.execute(select(StarAsset).where(StarAsset.id == asset_id))).scalar_one_or_none()
    if asset is None:
        return {"ok": False}
    planet = None
    if asset.planet_slug:
        planet = (
            await session.execute(select(Planet).where(Planet.slug == asset.planet_slug))
        ).scalar_one_or_none()
    snap = {}
    if planet:
        mastery = await gates.ensure_mastery(session, user.id, planet.id)
        snap = gates.record_learn_evidence(
            mastery,
            kind="starlib_read",
            ref_id=asset_id,
            detail=f"阅读《{asset.title}》p.{page}约{seconds}s",
        )
        await session.commit()
    return {"ok": True, "gates": snap}
