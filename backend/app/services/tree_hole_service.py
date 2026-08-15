import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tree_hole import MoodDiary, TreeHoleComment, TreeHoleLike, TreeHolePost, TreeHoleReaction
from app.models.user import User
from app.services.notification_service import create_notification

REACTION_EMOJIS = ["❤️", "😢", "😂", "😡", "🥺", "✨"]


MOODS = [
    {"key": "happy", "label": "开心", "icon": "✨"},
    {"key": "calm", "label": "平静", "icon": "🌙"},
    {"key": "tired", "label": "疲惫", "icon": "☁️"},
    {"key": "sad", "label": "低落", "icon": "🌧️"},
    {"key": "angry", "label": "烦躁", "icon": "⚡"},
]


def _parse_reaction_summary(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): int(v) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def _dump_reaction_summary(summary: dict[str, int]) -> str:
    return json.dumps(summary, ensure_ascii=False)


async def list_diaries(session: AsyncSession, user_id: str, limit: int = 30) -> list[dict]:
    rows = (
        await session.execute(
            select(MoodDiary).where(MoodDiary.user_id == user_id).order_by(MoodDiary.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "mood": r.mood,
            "content": r.content,
            "image_url": r.image_url,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def create_diary(
    session: AsyncSession, user_id: str, mood: str, content: str, image_url: str = ""
) -> dict:
    row = MoodDiary(
        id=str(uuid.uuid4()),
        user_id=user_id,
        mood=mood or "calm",
        content=content.strip(),
        image_url=image_url.strip(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "id": row.id,
        "mood": row.mood,
        "content": row.content,
        "image_url": row.image_url,
        "created_at": row.created_at.isoformat(),
    }


async def _serialize_post(
    session: AsyncSession,
    row: TreeHolePost,
    user_id: str,
    comment_count: int | None = None,
) -> dict:
    liked = (
        await session.execute(
            select(TreeHoleLike).where(TreeHoleLike.post_id == row.id, TreeHoleLike.user_id == user_id)
        )
    ).scalar_one_or_none()
    my_reactions = (
        await session.execute(
            select(TreeHoleReaction.emoji).where(TreeHoleReaction.post_id == row.id, TreeHoleReaction.user_id == user_id)
        )
    ).scalars().all()
    if comment_count is None:
        comment_count = (
            await session.execute(
                select(func.count()).select_from(TreeHoleComment).where(TreeHoleComment.post_id == row.id)
            )
        ).scalar_one()
    return {
        "id": row.id,
        "content": row.content,
        "image_url": row.image_url,
        "like_count": row.like_count,
        "liked_by_me": liked is not None,
        "reaction_summary": _parse_reaction_summary(row.reaction_summary),
        "my_reactions": list(my_reactions),
        "comment_count": int(comment_count or 0),
        "is_mine": row.user_id == user_id,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


async def list_posts(session: AsyncSession, user_id: str, limit: int = 40) -> list[dict]:
    rows = (
        await session.execute(select(TreeHolePost).order_by(TreeHolePost.created_at.desc()).limit(limit))
    ).scalars().all()
    out = []
    for row in rows:
        out.append(await _serialize_post(session, row, user_id))
    return out


async def create_post(session: AsyncSession, user_id: str, content: str, image_url: str = "") -> dict:
    row = TreeHolePost(
        id=str(uuid.uuid4()),
        user_id=user_id,
        content=content.strip(),
        image_url=image_url.strip(),
        reaction_summary="{}",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return await _serialize_post(session, row, user_id, comment_count=0)


async def delete_post(session: AsyncSession, user_id: str, post_id: str) -> bool:
    post = (
        await session.execute(
            select(TreeHolePost).where(TreeHolePost.id == post_id, TreeHolePost.user_id == user_id)
        )
    ).scalar_one_or_none()
    if post is None:
        return False
    for model in (TreeHoleComment, TreeHoleReaction, TreeHoleLike):
        rows = (
            await session.execute(select(model).where(model.post_id == post_id))
        ).scalars().all()
        for row in rows:
            await session.delete(row)
    await session.delete(post)
    await session.commit()
    return True


async def toggle_like(session: AsyncSession, user_id: str, post_id: str) -> dict:
    post = (await session.execute(select(TreeHolePost).where(TreeHolePost.id == post_id))).scalar_one_or_none()
    if post is None:
        raise ValueError("动态不存在")
    existing = (
        await session.execute(
            select(TreeHoleLike).where(TreeHoleLike.post_id == post_id, TreeHoleLike.user_id == user_id)
        )
    ).scalar_one_or_none()
    if existing:
        await session.delete(existing)
        post.like_count = max(0, post.like_count - 1)
        liked = False
    else:
        session.add(TreeHoleLike(id=str(uuid.uuid4()), post_id=post_id, user_id=user_id))
        post.like_count += 1
        liked = True
        if post.user_id != user_id:
            await create_notification(
                session,
                post.user_id,
                "树洞共鸣",
                "有人为你的匿名星轨点了共鸣",
                kind="tree_hole",
                link="treehole",
            )
    await session.commit()
    return {"like_count": post.like_count, "liked_by_me": liked}


async def react_post(session: AsyncSession, user_id: str, post_id: str, emoji: str) -> dict:
    if emoji not in REACTION_EMOJIS:
        raise ValueError("不支持的表情")
    post = (await session.execute(select(TreeHolePost).where(TreeHolePost.id == post_id))).scalar_one_or_none()
    if post is None:
        raise ValueError("动态不存在")
    summary = _parse_reaction_summary(post.reaction_summary)
    existing = (
        await session.execute(
            select(TreeHoleReaction).where(
                TreeHoleReaction.post_id == post_id,
                TreeHoleReaction.user_id == user_id,
                TreeHoleReaction.emoji == emoji,
            )
        )
    ).scalar_one_or_none()
    if existing:
        await session.delete(existing)
        summary[emoji] = max(0, summary.get(emoji, 0) - 1)
        if summary[emoji] == 0:
            summary.pop(emoji, None)
        toggled_on = False
    else:
        session.add(
            TreeHoleReaction(
                id=str(uuid.uuid4()),
                post_id=post_id,
                user_id=user_id,
                emoji=emoji,
            )
        )
        summary[emoji] = summary.get(emoji, 0) + 1
        toggled_on = True
        if post.user_id != user_id:
            await create_notification(
                session,
                post.user_id,
                "树洞互动",
                f"有人对你的匿名星轨表达了 {emoji}",
                kind="tree_hole",
                link="treehole",
            )
    post.reaction_summary = _dump_reaction_summary(summary)
    await session.commit()
    my_reactions = (
        await session.execute(
            select(TreeHoleReaction.emoji).where(TreeHoleReaction.post_id == post_id, TreeHoleReaction.user_id == user_id)
        )
    ).scalars().all()
    return {
        "reaction_summary": summary,
        "my_reactions": list(my_reactions),
        "toggled_on": toggled_on,
    }


async def list_comments(session: AsyncSession, post_id: str, limit: int = 80) -> list[dict]:
    post = (await session.execute(select(TreeHolePost).where(TreeHolePost.id == post_id))).scalar_one_or_none()
    if post is None:
        raise ValueError("动态不存在")
    rows = (
        await session.execute(
            select(TreeHoleComment)
            .where(TreeHoleComment.post_id == post_id)
            .order_by(TreeHoleComment.created_at.asc())
            .limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "post_id": r.post_id,
            "content": r.content,
            "emoji": r.emoji,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def create_comment(
    session: AsyncSession,
    user_id: str,
    post_id: str,
    content: str,
    emoji: str = "",
) -> dict:
    post = (await session.execute(select(TreeHolePost).where(TreeHolePost.id == post_id))).scalar_one_or_none()
    if post is None:
        raise ValueError("动态不存在")
    text = content.strip()
    if not text and not emoji:
        raise ValueError("评论内容不能为空")
    row = TreeHoleComment(
        id=str(uuid.uuid4()),
        post_id=post_id,
        user_id=user_id,
        content=text,
        emoji=emoji.strip(),
    )
    session.add(row)
    if post.user_id != user_id:
        await create_notification(
            session,
            post.user_id,
            "树洞评论",
            "有人评论了你的匿名星轨",
            kind="tree_hole",
            link="treehole",
        )
    await session.commit()
    await session.refresh(row)
    return {
        "id": row.id,
        "post_id": row.post_id,
        "content": row.content,
        "emoji": row.emoji,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
