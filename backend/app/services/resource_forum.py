"""聊天区资料站：帖子列表、发布、点赞、教师收录至星库、可引用附件。"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_resource import GeneratedResource
from app.models.resource_forum import ResourceForumPost
from app.models.star_asset import StarAsset
from app.models.user import User
from app.models.vault import VaultFile


def _post_out(row: ResourceForumPost, author_name: str = "") -> dict:
    return {
        "id": row.id,
        "author_id": row.author_id,
        "author_name": author_name,
        "class_id": row.class_id or "",
        "title": row.title,
        "body": row.body,
        "kind": row.kind or "note",
        "file_url": row.file_url or "",
        "source_type": getattr(row, "source_type", "") or "",
        "source_id": getattr(row, "source_id", "") or "",
        "like_count": int(row.like_count or 0),
        "promoted_asset_id": row.promoted_asset_id or "",
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


async def list_posts(
    session: AsyncSession,
    *,
    class_id: str = "",
    limit: int = 50,
) -> list[dict]:
    stmt = select(ResourceForumPost).order_by(ResourceForumPost.created_at.desc())
    if class_id:
        stmt = stmt.where(ResourceForumPost.class_id == class_id)
    rows = (await session.execute(stmt.limit(limit))).scalars().all()
    if not rows:
        return []
    author_ids = {r.author_id for r in rows}
    users = (
        await session.execute(select(User).where(User.id.in_(author_ids)))
    ).scalars().all()
    names = {u.id: u.display_name or u.username for u in users}
    return [_post_out(r, names.get(r.author_id, "匿名")) for r in rows]


async def create_post(
    session: AsyncSession,
    user: User,
    title: str,
    body: str,
    kind: str = "",
    file_url: str = "",
    source_type: str = "",
    source_id: str = "",
) -> dict:
    row = ResourceForumPost(
        author_id=user.id,
        class_id=user.class_id or "",
        title=title.strip(),
        body=body.strip(),
        kind=(kind or "note").strip() or "note",
        file_url=(file_url or "").strip(),
        source_type=(source_type or "").strip(),
        source_id=(source_id or "").strip()[:512],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _post_out(row, user.display_name or user.username)


async def list_attachable(session: AsyncSession, user: User, *, limit: int = 40) -> list[dict]:
    """聚合知识库近期文件、工坊文档、账号生成视频，供资料站选取。"""
    items: list[dict] = []

    vault_rows = (
        await session.execute(
            select(VaultFile)
            .where(VaultFile.user_id == user.id)
            .order_by(VaultFile.updated_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    for r in vault_rows:
        path = r.path or ""
        if path.endswith(".canvas") or "/.obsidian/" in path:
            continue
        items.append(
            {
                "id": path,
                "source_type": "vault",
                "title": r.title or path.split("/")[-1],
                "subtitle": path,
                "kind_label": "知识库",
                "file_url": "",
                "content_preview": "",
                "suggested_kind": "note" if path.endswith(".md") else "file",
            }
        )

    res_rows = (
        await session.execute(
            select(GeneratedResource)
            .where(GeneratedResource.user_id == user.id)
            .order_by(GeneratedResource.created_at.desc())
            .limit(80)
        )
    ).scalars().all()
    doc_kinds = {"doc", "reading", "deck", "code", "quiz", "mindmap"}
    for r in res_rows:
        meta = r.meta_json or {}
        media_url = str(meta.get("media_url") or "")
        if r.kind == "media" and media_url:
            items.append(
                {
                    "id": r.id,
                    "source_type": "video",
                    "title": r.title or "工坊视频",
                    "subtitle": r.planet_name or r.planet_slug or "",
                    "kind_label": "视频",
                    "file_url": media_url,
                    "content_preview": (r.content or "")[:280],
                    "suggested_kind": "file",
                }
            )
        elif r.kind in doc_kinds:
            items.append(
                {
                    "id": r.id,
                    "source_type": "workshop",
                    "title": r.title or f"工坊{r.kind}",
                    "subtitle": f"{r.kind} · {r.planet_name or r.planet_slug or ''}".strip(" ·"),
                    "kind_label": "工坊",
                    "file_url": str(meta.get("file_url") or meta.get("pptx_url") or ""),
                    "content_preview": (r.content or "")[:400],
                    "suggested_kind": "file" if (meta.get("file_url") or meta.get("pptx_url")) else "note",
                }
            )

    return items[: max(limit * 2, 60)]


async def like_post(session: AsyncSession, post_id: str) -> dict | None:
    row = (
        await session.execute(select(ResourceForumPost).where(ResourceForumPost.id == post_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    row.like_count = int(row.like_count or 0) + 1
    await session.commit()
    await session.refresh(row)
    author = (
        await session.execute(select(User).where(User.id == row.author_id))
    ).scalar_one_or_none()
    name = (author.display_name or author.username) if author else "匿名"
    return _post_out(row, name)


async def promote_to_starlib(
    session: AsyncSession,
    user: User,
    post_id: str,
    galaxy_slug: str = "",
    planet_slug: str = "",
) -> dict:
    if user.role not in ("teacher", "admin"):
        raise ValueError("需要教师或管理员权限")
    row = (
        await session.execute(select(ResourceForumPost).where(ResourceForumPost.id == post_id))
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("帖子不存在")
    if row.promoted_asset_id:
        raise ValueError("该帖子已收录至星库")

    asset = StarAsset(
        id=str(uuid.uuid4()),
        title=row.title.strip() or "资料站笔记",
        asset_type="note_pack",
        galaxy_slug=(galaxy_slug or "").strip(),
        planet_slug=(planet_slug or "").strip(),
        file_url=row.file_url or "",
        description=row.body.strip(),
        status="ready",
        owner_id=user.id,
        class_id=row.class_id or user.class_id or "",
        meta_json={
            "source": "resource_forum",
            "forum_post_id": row.id,
            "author_id": row.author_id,
            "kind": row.kind or "note",
            "body": row.body.strip(),
            "source_type": getattr(row, "source_type", "") or "",
            "source_id": getattr(row, "source_id", "") or "",
        },
    )
    session.add(asset)
    row.promoted_asset_id = asset.id
    await session.commit()
    await session.refresh(row)
    await session.refresh(asset)

    author = (
        await session.execute(select(User).where(User.id == row.author_id))
    ).scalar_one_or_none()
    name = (author.display_name or author.username) if author else "匿名"
    out = _post_out(row, name)
    out["star_asset"] = {
        "id": asset.id,
        "title": asset.title,
        "asset_type": asset.asset_type,
        "galaxy_slug": asset.galaxy_slug,
        "planet_slug": asset.planet_slug,
    }
    return out
