import json
from pathlib import Path

from typing import Optional, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import PETS_DIR
from app.models.user import User
from app.models.zone_extras import RedeemRecord
from app.schemas.pet import PetActionOut, PetManifestOut

FREE_PET_SLUGS = {"boxcat", "mallow", "ghost", "guami", "pupu"}
DEFAULT_PET_SLUG = "boxcat"

DEFAULT_CODEX_ACTIONS = [
    {"key": "idle", "label": "待机", "icon": "💤", "animation_row": 0, "frame_count": 6, "fps": 8, "loop": True, "route": ""},
    {"key": "walk", "label": "学习监督", "icon": "📚", "animation_row": 1, "frame_count": 8, "fps": 10, "loop": False, "route": "focus"},
    {"key": "run", "label": "去玩", "icon": "🎮", "animation_row": 2, "frame_count": 8, "fps": 12, "loop": False, "route": "leisure"},
    {"key": "wave", "label": "打招呼", "icon": "👋", "animation_row": 3, "frame_count": 4, "fps": 8, "loop": False, "route": "greet"},
    {"key": "laugh", "label": "战报", "icon": "📈", "animation_row": 4, "frame_count": 5, "fps": 8, "loop": False, "route": "report"},
    {"key": "think", "label": "错题", "icon": "📘", "animation_row": 5, "frame_count": 8, "fps": 8, "loop": False, "route": "mistakes"},
    {"key": "cheer", "label": "加油", "icon": "🔥", "animation_row": 6, "frame_count": 6, "fps": 10, "loop": False, "route": "greet"},
    {"key": "jump", "label": "跳跃", "icon": "⭐", "animation_row": 7, "frame_count": 6, "fps": 10, "loop": False, "route": ""},
    {"key": "wink", "label": "彩蛋", "icon": "✨", "animation_row": 8, "frame_count": 6, "fps": 8, "loop": False, "route": "bonus"},
]


def _load_manifest(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _parse_actions(data: dict, fmt: str, default_frame: int) -> list[PetActionOut]:
    raw = data.get("actions")
    if not isinstance(raw, list) or not raw:
        raw = DEFAULT_CODEX_ACTIONS if fmt == "codex" else [
            {"key": "idle", "label": "待机", "icon": "💤", "animation_row": 0, "frame_count": default_frame, "fps": 8, "loop": True, "route": ""},
            {"key": "wave", "label": "打招呼", "icon": "👋", "animation_row": 0, "frame_count": default_frame, "fps": 12, "loop": False, "route": "greet"},
            {"key": "walk", "label": "学习监督", "icon": "📚", "animation_row": 0, "frame_count": default_frame, "fps": 10, "loop": False, "route": "focus"},
            {"key": "laugh", "label": "战报", "icon": "📈", "animation_row": 0, "frame_count": default_frame, "fps": 10, "loop": False, "route": "report"},
            {"key": "think", "label": "错题", "icon": "📘", "animation_row": 0, "frame_count": default_frame, "fps": 10, "loop": False, "route": "mistakes"},
            {"key": "run", "label": "去玩", "icon": "🎮", "animation_row": 0, "frame_count": default_frame, "fps": 12, "loop": False, "route": "leisure"},
            {"key": "cheer", "label": "加油", "icon": "🔥", "animation_row": 0, "frame_count": default_frame, "fps": 10, "loop": False, "route": "greet"},
            {"key": "jump", "label": "跳跃", "icon": "⭐", "animation_row": 0, "frame_count": default_frame, "fps": 10, "loop": False, "route": ""},
            {"key": "wink", "label": "彩蛋", "icon": "✨", "animation_row": 0, "frame_count": default_frame, "fps": 12, "loop": False, "route": "bonus"},
        ]
    out: list[PetActionOut] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            PetActionOut(
                key=str(item.get("key", "idle")),
                label=str(item.get("label", "动作")),
                icon=str(item.get("icon", "✨")),
                animation_row=int(item.get("animation_row", 0)),
                frame_count=int(item.get("frame_count", default_frame)),
                fps=int(item.get("fps", 8)),
                loop=bool(item.get("loop", False)),
                route=str(item.get("route", "")),
            )
        )
    return out


def affinity_level(affinity: int) -> tuple[int, str]:
    if affinity >= 200:
        return 4, "星轨挚友"
    if affinity >= 100:
        return 3, "默契伙伴"
    if affinity >= 50:
        return 2, "熟悉好友"
    if affinity >= 20:
        return 1, "初识"
    return 0, "陌生"


def list_pet_manifests() -> list[PetManifestOut]:
    pets: list[PetManifestOut] = []
    if not PETS_DIR.exists():
        return pets

    for folder in sorted(PETS_DIR.iterdir()):
        if not folder.is_dir():
            continue
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            continue
        data = _load_manifest(manifest_path)
        slug = data.get("slug") or data.get("id") or folder.name
        pet_json = folder / "pet.json"
        if pet_json.exists():
            data = {**_load_manifest(pet_json), **data}
        frames = data.get("frames") or data.get("animations", {}).get("idle", {}).get("frames", [])
        spritesheet = data.get("spritesheet") or data.get("spritesheetPath") or data.get("preview") or "spritesheet.webp"
        preview = data.get("preview") or spritesheet
        columns = int(data.get("columns", 1))
        rows = int(data.get("rows", 1))
        frame_count = len(frames) if isinstance(frames, list) and frames else int(
            data.get("frame_count", 6 if data.get("format") == "codex" or (columns == 8 and rows == 9) else columns * rows)
        )
        fmt = str(data.get("format") or ("codex" if columns == 8 and rows == 9 else "spritesheet"))
        sprite_url = f"/static/assets/pets/{slug}/{spritesheet}"
        pets.append(
            PetManifestOut(
                slug=slug,
                name=str(data.get("name") or data.get("displayName") or slug),
                description=str(data.get("description", "")),
                preview_url=preview if str(preview).startswith("/") else f"/static/assets/pets/{slug}/{preview}",
                manifest_url=f"/static/assets/pets/{slug}/manifest.json",
                sprite_url=sprite_url if sprite_url.startswith("/") else f"/static/assets/pets/{slug}/{spritesheet}",
                format=fmt,
                columns=columns,
                rows=rows,
                cell_width=int(data.get("cell_width", 0)),
                cell_height=int(data.get("cell_height", 0)),
                sheet_width=int(data.get("sheet_width", 0)),
                sheet_height=int(data.get("sheet_height", 0)),
                animation_row=int(data.get("animation_row", 0)),
                frame_count=frame_count,
                fps=int(data.get("fps", 12)),
                actions=_parse_actions(data, fmt, frame_count),
            )
        )
    return pets


def available_pet_slugs() -> set[str]:
    return {p.slug for p in list_pet_manifests()}


def resolve_pet_slug(pet_slug: Optional[str]) -> str:
    """若当前 slug 无效（旧宠已删），回落到默认免费宠。"""
    available = available_pet_slugs()
    slug = (pet_slug or "").strip()
    if slug and slug in available:
        return slug
    if DEFAULT_PET_SLUG in available:
        return DEFAULT_PET_SLUG
    return next(iter(sorted(available)), "")


async def list_owned_pet_slugs(session: AsyncSession, user: User) -> Set[str]:
    owned: Set[str] = set(FREE_PET_SLUGS)
    rows = (
        await session.execute(select(RedeemRecord.item_id).where(RedeemRecord.user_id == user.id))
    ).scalars().all()
    from app.services.zone_extras import SHOP_ITEMS

    catalog = {x["id"]: x for x in SHOP_ITEMS if x.get("kind") == "pet"}
    for item_id in rows:
        meta = catalog.get(item_id) or {}
        slug = str(meta.get("pet_slug") or "").strip()
        if slug:
            owned.add(slug)
    current = (user.pet_slug or "").strip()
    if current and current in available_pet_slugs():
        owned.add(current)
    return owned


async def set_user_pet(session: AsyncSession, user: User, pet_slug: str) -> User:
    exists = any(p.slug == pet_slug for p in list_pet_manifests())
    if not exists:
        raise ValueError("桌宠不存在")
    owned = await list_owned_pet_slugs(session, user)
    if pet_slug not in owned and pet_slug not in FREE_PET_SLUGS:
        raise ValueError("尚未解锁该桌宠，请先在积分商城兑换")
    user.pet_slug = pet_slug
    await session.commit()
    await session.refresh(user)
    return user


async def bump_pet_affinity(session: AsyncSession, user: User, delta: int = 1) -> dict:
    user.pet_affinity = int(user.pet_affinity or 0) + max(1, min(20, delta))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    level, name = affinity_level(user.pet_affinity)
    return {"pet_affinity": user.pet_affinity, "level": level, "level_name": name}


async def set_equipped_title(session: AsyncSession, user: User, title_id: str) -> User:
    tid = title_id.strip()
    if tid:
        from app.services.zone_extras import SHOP_ITEMS

        catalog_ids = {x["id"] for x in SHOP_ITEMS if x.get("kind") == "title"}
        if tid not in catalog_ids:
            raise ValueError("无效称号")
        owned = (
            await session.execute(
                select(RedeemRecord.item_id).where(
                    RedeemRecord.user_id == user.id,
                    RedeemRecord.item_id == tid,
                )
            )
        ).scalar_one_or_none()
        if not owned:
            raise ValueError("尚未拥有该称号，请先在商城兑换")
    user.equipped_title = tid
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def set_study_theme(session: AsyncSession, user: User, theme_id: str) -> User:
    user.study_theme = theme_id.strip()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
