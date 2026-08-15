import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Galaxy, Planet
from app.models.note import LessonResource, Note
from app.models.user import User
from app.services import mastery_gates as gates
from app.services.rag import build_rag_context
from app.services.spark import spark_chat


def _note_out(r: Note) -> dict:
    return {
        "id": r.id,
        "planet_slug": r.planet_slug,
        "galaxy_slug": getattr(r, "galaxy_slug", None) or "",
        "title": r.title,
        "content": r.content,
        "attachment_url": r.attachment_url,
        "blocks_json": r.blocks_json or [],
        "source": getattr(r, "source", None) or "manual",
        "session_id": getattr(r, "session_id", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


async def _resolve_galaxy_slug(session: AsyncSession, planet_slug: str, galaxy_slug: str = "") -> str:
    if galaxy_slug.strip():
        return galaxy_slug.strip()
    if not planet_slug.strip():
        return ""
    planet = (
        await session.execute(select(Planet).where(Planet.slug == planet_slug.strip()))
    ).scalar_one_or_none()
    if not planet:
        return ""
    galaxy = (
        await session.execute(select(Galaxy).where(Galaxy.id == planet.galaxy_id))
    ).scalar_one_or_none()
    return galaxy.slug if galaxy else ""


async def list_notes(
    session: AsyncSession,
    user_id: str,
    *,
    planet_slug: str = "",
    galaxy_slug: str = "",
    q: str = "",
) -> list[dict]:
    stmt = select(Note).where(Note.user_id == user_id).order_by(Note.updated_at.desc())
    if planet_slug:
        stmt = stmt.where(Note.planet_slug == planet_slug)
    if galaxy_slug:
        # 中笔记：本星系所有行星（含仅有 galaxy_slug 的笔记）
        stmt = stmt.where(Note.galaxy_slug == galaxy_slug)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Note.title.ilike(like), Note.content.ilike(like), Note.planet_slug.ilike(like)))
    rows = (await session.execute(stmt.limit(500))).scalars().all()
    return [_note_out(r) for r in rows]


async def create_note(
    session: AsyncSession,
    user_id: str,
    *,
    title: str,
    content: str,
    planet_slug: str = "",
    galaxy_slug: str = "",
    attachment_url: str = "",
    blocks_json: list | None = None,
    source: str = "manual",
    session_id: str = "",
) -> dict:
    now = datetime.now(timezone.utc)
    gslug = await _resolve_galaxy_slug(session, planet_slug, galaxy_slug)
    row = Note(
        id=str(uuid.uuid4()),
        user_id=user_id,
        planet_slug=planet_slug.strip(),
        galaxy_slug=gslug,
        title=title.strip() or "未命名笔记",
        content=content.strip(),
        attachment_url=attachment_url.strip(),
        blocks_json=blocks_json or [],
        source=source or "manual",
        session_id=session_id or "",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    if planet_slug.strip():
        planet = (
            await session.execute(select(Planet).where(Planet.slug == planet_slug.strip()))
        ).scalar_one_or_none()
        if planet:
            mastery = await gates.ensure_mastery(session, user_id, planet.id)
            gates.record_learn_evidence(
                mastery,
                kind="note",
                ref_id=row.id,
                detail=row.title[:80],
            )
    await session.commit()
    await session.refresh(row)
    return _note_out(row)


async def update_note(
    session: AsyncSession,
    user_id: str,
    note_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    blocks_json: list | None = None,
    attachment_url: str | None = None,
) -> dict | None:
    row = (
        await session.execute(select(Note).where(Note.id == note_id, Note.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        return None
    if title is not None:
        row.title = title.strip() or row.title
    if content is not None:
        row.content = content
    if blocks_json is not None:
        row.blocks_json = blocks_json
    if attachment_url is not None:
        row.attachment_url = attachment_url
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _note_out(row)


async def _sync_clip_to_vault(
    session: AsyncSession,
    user_id: str,
    *,
    planet_slug: str,
    title: str,
    content: str,
    source: str,
    galaxy_slug: str = "",
) -> None:
    """将剪藏同步写入星轨知识库 20-Clips/（失败不影响主流程）。"""
    try:
        from app.services import vault_service as vault_svc

        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            return
        gslug = galaxy_slug or await _resolve_galaxy_slug(session, planet_slug)
        await vault_svc.ingest_clip(
            session,
            user,
            title=title or source or "学习剪藏",
            content=content or "剪藏",
            planet_slug=planet_slug,
            galaxy_slug=gslug,
            source=source or "clip",
        )
    except Exception:
        pass


async def clip_to_note(
    session: AsyncSession,
    user_id: str,
    *,
    planet_slug: str,
    block: dict,
    title: str = "",
) -> dict:
    """将一张卡片追加到最新笔记，或新建。"""
    stmt = (
        select(Note)
        .where(Note.user_id == user_id, Note.planet_slug == planet_slug)
        .order_by(Note.updated_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    block = dict(block or {})
    block.setdefault("at", now.isoformat())
    clip_text = str(block.get("text") or block.get("narrate") or "剪藏")
    clip_source = str(block.get("kind") or "clip")
    clip_title = title or clip_source or "学习剪藏"

    if row is None:
        out = await create_note(
            session,
            user_id,
            title=clip_title,
            content=clip_text,
            planet_slug=planet_slug,
            blocks_json=[block],
            source=clip_source,
        )
        await _sync_clip_to_vault(
            session,
            user_id,
            planet_slug=planet_slug,
            title=clip_title,
            content=clip_text,
            source=clip_source,
            galaxy_slug=str(out.get("galaxy_slug") or ""),
        )
        return out

    blocks = list(row.blocks_json or [])
    blocks.append(block)
    row.blocks_json = blocks[-50:]
    if block.get("text") or block.get("narrate"):
        row.content = (row.content + "\n\n" + str(block.get("text") or block.get("narrate")))[:8000]
    if not getattr(row, "galaxy_slug", None):
        row.galaxy_slug = await _resolve_galaxy_slug(session, planet_slug)
    row.updated_at = now
    session.add(row)
    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if planet:
        mastery = await gates.ensure_mastery(session, user_id, planet.id)
        gates.record_learn_evidence(mastery, kind="note_clip", ref_id=row.id, detail=clip_source)
    await session.commit()
    await session.refresh(row)
    await _sync_clip_to_vault(
        session,
        user_id,
        planet_slug=planet_slug,
        title=clip_title,
        content=clip_text if clip_text != "剪藏" else str(row.content or "剪藏"),
        source=clip_source,
        galaxy_slug=getattr(row, "galaxy_slug", "") or "",
    )
    return _note_out(row)


async def ai_summary_note(
    session: AsyncSession,
    user_id: str,
    *,
    planet_slug: str,
) -> dict:
    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    name = planet.name if planet else planet_slug
    rag = build_rag_context(name)
    existing = await list_notes(session, user_id, planet_slug=planet_slug)
    clips = []
    for n in existing[:5]:
        clips.extend(n.get("blocks_json") or [])
    prompt = f"""根据知识点「{name}」与学生剪藏，生成一份结构化随堂笔记（Markdown）。
{rag}
已有剪藏：{json_dumps(clips[:12])}
包含：学习目标、核心要点、演武关键步、易错点、待复习。文末列出引用页码（若有）。"""
    text = await spark_chat(
        [
            {"role": "system", "content": "你是星轨学图笔记助手，输出中文 Markdown。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
    )
    body = (text or f"# {name}\n\n- 要点整理中…").strip()
    return await create_note(
        session,
        user_id,
        title=f"{name} · 随堂笔记",
        content=body,
        planet_slug=planet_slug,
        blocks_json=[{"kind": "ai_summary", "text": body[:500]}],
        source="ai_summary",
    )


def json_dumps(obj) -> str:
    import json

    try:
        return json.dumps(obj, ensure_ascii=False)[:3000]
    except Exception:
        return "[]"


async def delete_note(session: AsyncSession, user_id: str, note_id: str) -> bool:
    row = (
        await session.execute(select(Note).where(Note.id == note_id, Note.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


_VALID_RESOURCE_KINDS = frozenset({"book", "deck", "quiz", "plan", "video", "other"})


def _normalize_resource_kind(kind: str) -> str:
    k = (kind or "other").strip().lower()
    return k if k in _VALID_RESOURCE_KINDS else "other"


def _lesson_resource_out(r: LessonResource) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "galaxy_slug": r.galaxy_slug,
        "file_url": r.file_url,
        "class_id": r.class_id,
        "resource_kind": getattr(r, "resource_kind", None) or "other",
        "promoted_asset_id": getattr(r, "promoted_asset_id", None) or "",
        "created_at": r.created_at.isoformat() if r.created_at else "",
    }


async def create_lesson_resource(
    session: AsyncSession,
    teacher: User,
    *,
    title: str,
    galaxy_slug: str,
    file_url: str,
    class_id: str = "",
    resource_kind: str = "other",
) -> dict:
    row = LessonResource(
        id=str(uuid.uuid4()),
        teacher_id=teacher.id,
        class_id=class_id or teacher.class_id or "",
        galaxy_slug=galaxy_slug.strip(),
        title=title.strip() or "未命名资料",
        file_url=file_url.strip(),
        resource_kind=_normalize_resource_kind(resource_kind),
        promoted_asset_id="",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _lesson_resource_out(row)


async def create_lesson_resource_from_text(
    session: AsyncSession,
    teacher: User,
    *,
    title: str,
    content: str,
    galaxy_slug: str = "",
    class_id: str = "",
    resource_kind: str = "plan",
) -> dict:
    """将 Markdown/文本写入本地文件并登记为教学资料。"""
    from app.core.paths import RESOURCES_DIR, ensure_storage_dirs

    ensure_storage_dirs()
    safe_name = f"{uuid.uuid4().hex[:12]}.md"
    path = RESOURCES_DIR / safe_name
    path.write_text(content.strip(), encoding="utf-8")
    file_url = f"/static/uploads/resources/{safe_name}"
    return await create_lesson_resource(
        session,
        teacher,
        title=title.strip() or "未命名教案",
        galaxy_slug=galaxy_slug,
        file_url=file_url,
        class_id=class_id,
        resource_kind=resource_kind or "plan",
    )


async def list_lesson_resources(
    session: AsyncSession,
    user: User,
    galaxy_slug: str = "",
    resource_kind: str = "",
) -> list[dict]:
    stmt = select(LessonResource)
    if user.role == "student" and user.class_id:
        stmt = stmt.where(LessonResource.class_id == user.class_id)
    elif user.role == "teacher":
        stmt = stmt.where(LessonResource.teacher_id == user.id)
    if galaxy_slug:
        stmt = stmt.where(LessonResource.galaxy_slug == galaxy_slug)
    if resource_kind:
        stmt = stmt.where(LessonResource.resource_kind == _normalize_resource_kind(resource_kind))
    rows = (await session.execute(stmt.order_by(LessonResource.created_at.desc()))).scalars().all()
    return [_lesson_resource_out(r) for r in rows]


async def delete_lesson_resource(session: AsyncSession, teacher: User, resource_id: str) -> bool:
    row = (
        await session.execute(
            select(LessonResource).where(LessonResource.id == resource_id, LessonResource.teacher_id == teacher.id)
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def promote_lesson_resource_to_starlib(
    session: AsyncSession,
    teacher: User,
    resource_id: str,
    *,
    class_id: str = "",
    galaxy_slug: str = "",
    planet_slug: str = "",
    asset_type: str = "note_pack",
) -> dict:
    """将教师资料升格为班级星库资产。"""
    from app.models.star_asset import StarAsset

    if teacher.role not in ("teacher", "admin"):
        raise ValueError("需要教师或管理员权限")
    row = (
        await session.execute(
            select(LessonResource).where(LessonResource.id == resource_id, LessonResource.teacher_id == teacher.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("资料不存在")
    if getattr(row, "promoted_asset_id", None):
        raise ValueError("该资料已发布到星库")

    kind_to_asset = {
        "book": "book",
        "deck": "note_pack",
        "quiz": "problem_doc",
        "plan": "note_pack",
        "other": "note_pack",
    }
    rkind = getattr(row, "resource_kind", None) or "other"
    atype = asset_type if asset_type in ("book", "pdf", "problem_doc", "note_pack") else kind_to_asset.get(rkind, "note_pack")
    cid = (class_id or row.class_id or teacher.class_id or "").strip()
    gslug = (galaxy_slug or row.galaxy_slug or "").strip()

    asset = StarAsset(
        id=str(uuid.uuid4()),
        title=row.title.strip() or "教学资料",
        asset_type=atype,
        galaxy_slug=gslug,
        planet_slug=(planet_slug or "").strip(),
        file_url=row.file_url or "",
        description=f"教师知识库发布 · {rkind}",
        status="ready",
        owner_id=teacher.id,
        class_id=cid,
        meta_json={
            "source": "teacher_knowledge",
            "lesson_resource_id": row.id,
            "resource_kind": rkind,
        },
    )
    session.add(asset)
    row.promoted_asset_id = asset.id
    if cid and not row.class_id:
        row.class_id = cid
    await session.commit()
    await session.refresh(row)
    await session.refresh(asset)
    out = _lesson_resource_out(row)
    out["star_asset"] = {
        "id": asset.id,
        "title": asset.title,
        "asset_type": asset.asset_type,
        "galaxy_slug": asset.galaxy_slug,
        "planet_slug": asset.planet_slug,
        "class_id": asset.class_id,
    }
    return out


async def promote_generated_to_starlib(
    session: AsyncSession,
    teacher: User,
    resource_id: str,
    *,
    class_id: str = "",
    galaxy_slug: str = "",
    planet_slug: str = "",
) -> dict:
    """将 AI 生成资源写入资料库并升格星库。"""
    from app.models.generated_resource import GeneratedResource

    gen = (
        await session.execute(
            select(GeneratedResource).where(
                GeneratedResource.id == resource_id,
                GeneratedResource.user_id == teacher.id,
            )
        )
    ).scalar_one_or_none()
    if gen is None:
        raise ValueError("生成资源不存在")

    kind_map = {"deck": "deck", "quiz": "quiz", "doc": "plan", "mindmap": "other", "reading": "other"}
    rkind = kind_map.get(gen.kind, "other")
    lesson = await create_lesson_resource_from_text(
        session,
        teacher,
        title=gen.title or f"{gen.kind} · {gen.planet_name}",
        content=gen.content or "",
        galaxy_slug=galaxy_slug or "",
        class_id=class_id,
        resource_kind=rkind,
    )
    return await promote_lesson_resource_to_starlib(
        session,
        teacher,
        lesson["id"],
        class_id=class_id,
        galaxy_slug=galaxy_slug or "",
        planet_slug=planet_slug or gen.planet_slug or "",
    )
