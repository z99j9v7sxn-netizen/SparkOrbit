"""星际造物主 AIGC：PDF 讲义解析 → 自动生成星系与行星。"""
import re
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Galaxy, Planet
from app.services.rag import ingest_syllabus
from app.services.spark import extract_json, spark_chat

try:
    from pypdf import PdfReader  # type: ignore

    _PDF_AVAILABLE = True
except ImportError:
    PdfReader = None  # type: ignore
    _PDF_AVAILABLE = False


def extract_pdf_text(data: bytes) -> str:
    if not _PDF_AVAILABLE or not data:
        return ""
    import io

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages[:30]:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _slugify(name: str) -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff]+", "-", name.strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:48] or f"galaxy-{uuid.uuid4().hex[:6]}"


async def _parse_structure(text: str, title_hint: str = "") -> Dict[str, Any]:
    system = (
        "你是 SparkOrbit 星际造物主。请从教学讲义中抽取知识层级，生成一个星系及其行星。"
        "严格返回 JSON："
        '{"galaxy":{"name":"星系名","description":"简介","color":"#hex"},'
        '"planets":[{"name":"知识点名","description":"说明","difficulty":"easy|medium|hard","prerequisites":[]}]}'
        "行星 5-12 个，prerequisites 用行星 slug（小写英文连字符）。"
    )
    snippet = text[:6000]
    user = f"讲义标题提示：{title_hint}\n讲义内容：\n{snippet}\n请抽取结构。"
    raw = await spark_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.5,
    )
    data = extract_json(raw) if raw else None
    if not data or "galaxy" not in data:
        return {
            "galaxy": {
                "name": title_hint or "自定义星系",
                "description": "由 PDF 讲义自动生成的知识星系",
                "color": "#6366f1",
            },
            "planets": [
                {"name": f"知识点 {i+1}", "description": "自动抽取", "difficulty": "medium", "prerequisites": []}
                for i in range(6)
            ],
        }
    return data


async def forge_galaxy_from_pdf(
    session: AsyncSession,
    pdf_bytes: bytes,
    title_hint: str = "",
) -> Dict[str, Any]:
    text = extract_pdf_text(pdf_bytes)
    if not text:
        text = title_hint or "通用教学讲义"

    structure = await _parse_structure(text, title_hint)
    g_data = structure.get("galaxy") or {}
    g_name = str(g_data.get("name", title_hint or "自定义星系"))
    g_slug = _slugify(g_name)

    existing = (await session.execute(select(Galaxy).where(Galaxy.slug == g_slug))).scalar_one_or_none()
    if existing:
        g_slug = f"{g_slug}-{uuid.uuid4().hex[:4]}"

    max_order = (
        await session.execute(select(Galaxy.sort_order))
    ).scalars().all()
    sort_order = (max(max_order) if max_order else 0) + 1

    galaxy = Galaxy(
        slug=g_slug,
        name=g_name,
        description=str(g_data.get("description", "")),
        color=str(g_data.get("color", "#6366f1")),
        orbit_radius=28.0 + sort_order * 2,
        sort_order=sort_order,
        is_active=True,
    )
    session.add(galaxy)
    await session.flush()

    planets_data: List[dict] = structure.get("planets") or []
    slug_registry: Dict[str, str] = {}
    created_planets: List[dict] = []

    for i, p in enumerate(planets_data[:15]):
        p_name = str(p.get("name", f"知识点{i+1}"))
        p_slug = _slugify(p_name)
        if p_slug in slug_registry:
            p_slug = f"{p_slug}-{i}"
        slug_registry[p_name] = p_slug

        pre_slugs = []
        for pre in p.get("prerequisites") or []:
            pre_str = str(pre)
            if pre_str in slug_registry.values():
                pre_slugs.append(pre_str)
            elif pre_str in slug_registry:
                pre_slugs.append(slug_registry[pre_str])

        planet = Planet(
            galaxy_id=galaxy.id,
            slug=p_slug,
            name=p_name,
            description=str(p.get("description", "")),
            difficulty=str(p.get("difficulty", "medium")),
            orbit_index=int(p.get("orbit_index", (i % 4) + 1)),
            angle_deg=float((i * 37) % 360),
            radius_offset=0.0,
            prerequisites=pre_slugs,
            question_tags=[p_name],
            sort_order=i,
        )
        session.add(planet)
        created_planets.append({"slug": p_slug, "name": p_name})

    await session.commit()
    await session.refresh(galaxy)

    rag_count = ingest_syllabus(galaxy.slug, text, source="pdf_forge")

    return {
        "galaxy_id": galaxy.id,
        "galaxy_slug": galaxy.slug,
        "galaxy_name": galaxy.name,
        "planet_count": len(created_planets),
        "planets": created_planets,
        "rag_chunks": rag_count,
        "pdf_available": _PDF_AVAILABLE,
    }
