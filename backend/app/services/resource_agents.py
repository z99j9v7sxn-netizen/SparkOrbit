"""多智能体协同资源生成编排器（Coordinator + 6 类 Resource Agent）。"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Dict, List, Literal, Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_resource import GeneratedResource
from app.models.galaxy import Planet
from app.models.student_profile import PROFILE_DIMENSIONS
from app.models.user import User
from app.core.config import get_settings
from app.services.llm import extract_json, llm_available, llm_chat, llm_chat_stream
from app.services.profiles import get_latest_profile
from app.services.rag import build_rag_context, retrieve_citations
from app.services.resource_quality import quality_summary, score_resource
from app.services.media_provenance import validate_slides_provenance
from app.services.media_captions import (
    build_caption_cues,
    build_teaching_seedance_prompt,
    burn_subtitles_into_mp4,
)
from app.services.seedance_service import (
    compose_seedance_prompt,
    create_video_task,
    download_video,
    extract_video_url,
    get_video_task,
    seedance_available,
)

AgentRole = Literal["Coordinator", "DocAgent", "MindAgent", "QuizAgent", "ReadAgent", "MediaAgent", "DeckAgent", "CodeAgent", "System"]
ResourceKind = Literal["doc", "mindmap", "quiz", "reading", "media", "deck", "code"]

AGENT_LABELS: dict[ResourceKind, tuple[AgentRole, str]] = {
    "doc": ("DocAgent", "讲解文档 Agent"),
    "mindmap": ("MindAgent", "思维导图 Agent"),
    "quiz": ("QuizAgent", "题库 Agent"),
    "reading": ("ReadAgent", "拓展阅读 Agent"),
    "media": ("MediaAgent", "教学动画 Agent"),
    "deck": ("DeckAgent", "教学课件 Agent"),
    "code": ("CodeAgent", "代码实操 Agent"),
}

_RUNS: Dict[str, Dict[str, Any]] = {}


def _runs_dir() -> "Path":
    from pathlib import Path

    base = Path(__file__).resolve().parents[2] / "data" / "resource_runs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _persist_run(run_id: str, params: Dict[str, Any]) -> None:
    """内存 + 磁盘双写，重启后仍可解析元数据（SSE 事件本身仍需重新拉流）。"""
    from datetime import datetime, timezone
    from pathlib import Path

    payload = {
        **params,
        "id": run_id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _RUNS[run_id] = payload
    try:
        path = _runs_dir() / f"{run_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        # 磁盘失败不阻断演示；内存仍可用
        pass


def _load_run_from_disk(run_id: str) -> Optional[Dict[str, Any]]:
    from pathlib import Path

    path = _runs_dir() / f"{run_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            _RUNS[run_id] = data
            return data
    except Exception:  # noqa: BLE001
        return None
    return None


class ResourceEvent(TypedDict):
    role: AgentRole
    type: str
    content: str
    payload: Dict[str, Any]


def register_resource_run(run_id: str, params: Dict[str, Any]) -> None:
    merged = dict(params)
    merged.setdefault("status", "registered")
    _persist_run(run_id, merged)


def get_resource_run(run_id: str) -> Optional[Dict[str, Any]]:
    hit = _RUNS.get(run_id)
    if hit is not None:
        return hit
    return _load_run_from_disk(run_id)


def update_resource_run_status(run_id: str, status: str, **extra: Any) -> None:
    cur = get_resource_run(run_id) or {"id": run_id}
    cur.update(extra)
    cur["status"] = status
    _persist_run(run_id, cur)


def format_resource_sse(event: ResourceEvent) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _emit(
    role: AgentRole,
    event_type: str,
    content: str,
    payload: Optional[Dict[str, Any]] = None,
    delay: float = 0.08,
) -> ResourceEvent:
    await asyncio.sleep(delay)
    return {"role": role, "type": event_type, "content": content, "payload": payload or {}}


def _profile_brief(profile) -> str:
    if profile is None:
        return "暂无画像，按通用大学生水平生成。"
    lines = []
    for dim in PROFILE_DIMENSIONS:
        data = getattr(profile, dim, {}) or {}
        if isinstance(data, dict):
            lines.append(f"- {dim}: {data.get('value', '未知')} (分数 {data.get('score', 50)})")
    strategy = []
    modality = getattr(profile, "modality_preference", None) or {}
    motive = getattr(profile, "motivation_level", None) or {}
    if isinstance(modality, dict) and modality.get("value"):
        strategy.append(f"优先模态：{modality.get('value')}")
    if isinstance(motive, dict) and motive.get("value"):
        strategy.append(f"动机策略：{motive.get('value')}（分数 {motive.get('score', 50)}）")
    brief = "\n".join(lines) + f"\n摘要: {getattr(profile, 'summary', '')}"
    if strategy:
        brief += "\n生成策略: " + "；".join(strategy)
    return brief


def _sort_kinds_by_profile(kinds: List[ResourceKind], profile) -> List[ResourceKind]:
    if not profile:
        return list(kinds)
    data = getattr(profile, "modality_preference", None) or {}
    text = str(data.get("value") or "") if isinstance(data, dict) else ""
    preferred: list[str] = []
    if any(k in text for k in ("视听", "视频", "动画")):
        preferred = ["media", "deck", "doc", "quiz", "code", "mindmap", "reading"]
    elif any(k in text for k in ("实操", "代码", "动手", "编程")):
        preferred = ["code", "quiz", "doc", "media", "mindmap", "deck", "reading"]
    elif any(k in text for k in ("文本", "阅读", "文档", "看书")):
        preferred = ["doc", "reading", "mindmap", "quiz", "deck", "media", "code"]
    if not preferred:
        return list(kinds)
    rank = {k: i for i, k in enumerate(preferred)}
    return sorted(list(kinds), key=lambda k: rank.get(k, 99))


async def _get_planet(session: AsyncSession, slug: str) -> Optional[Planet]:
    return (await session.execute(select(Planet).where(Planet.slug == slug))).scalar_one_or_none()


async def _save_resource(
    session: AsyncSession,
    user_id: str,
    planet: Planet,
    kind: ResourceKind,
    title: str,
    content: str,
    meta: dict,
) -> GeneratedResource:
    row = GeneratedResource(
        id=str(uuid.uuid4()),
        user_id=user_id,
        planet_slug=planet.slug,
        planet_name=planet.name,
        kind=kind,
        title=title,
        content=content,
        meta_json=meta,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 各 Resource Agent
# ---------------------------------------------------------------------------

async def _agent_doc(planet: Planet, profile_brief: str, rag: str, extra: str) -> tuple[str, str, dict]:
    prompt = f"""你是 DocAgent，为学生生成个性化讲解文档（Markdown）。
知识点：{planet.name} — {planet.description}
学生画像：
{profile_brief}
参考资料：{rag[:1200]}
额外要求：{extra or '无'}

请输出完整 Markdown 文档，包含：# 标题、## 核心概念、## 原理讲解、## 案例、## 总结。篇幅 600-1000 字，根据画像调整深浅。"""
    if llm_available():
        text = await llm_chat(
            [{"role": "system", "content": "你是专业的课程讲解文档生成 Agent。"}, {"role": "user", "content": prompt}],
            temperature=0.6,
        )
        if text:
            return f"{planet.name} 讲解文档", text.strip(), {}
    fallback = f"""# {planet.name}

## 核心概念
{planet.description or '本知识点是课程体系中的重要一环。'}

## 原理讲解
建议结合教材定义与典型应用场景理解，注意区分易混淆概念。

## 案例
通过一个最小可运行/可推导的例子建立直觉，再推广到一般情形。

## 总结
- 回顾关键术语
- 列出 2-3 个自测问题
"""
    return f"{planet.name} 讲解文档", fallback, {"fallback": True}


async def _agent_mindmap(planet: Planet, profile_brief: str, rag: str, extra: str) -> tuple[str, str, dict]:
    prompt = f"""你是 MindAgent，为知识点「{planet.name}」生成思维导图 JSON 树。
返回纯 JSON：{{"name":"根节点","children":[{{"name":"子节点","children":[]}}]}}
要求 3-4 层深度，6-12 个叶子节点。画像：{profile_brief[:400]}"""
    tree: dict = {"name": planet.name, "children": [{"name": "核心概念", "children": [{"name": "定义"}, {"name": "性质"}]}, {"name": "应用", "children": [{"name": "例题"}, {"name": "易错点"}]}]}
    if llm_available():
        raw = await llm_chat(
            [{"role": "system", "content": "只输出 JSON 对象，不要 Markdown。"}, {"role": "user", "content": prompt}],
            temperature=0.4,
            response_json=True,
        )
        if raw:
            parsed = extract_json(raw) or json.loads(raw) if raw.strip().startswith("{") else None
            if isinstance(parsed, dict) and parsed.get("name"):
                tree = parsed
    return f"{planet.name} 思维导图", json.dumps(tree, ensure_ascii=False), {"tree": tree}


async def _agent_quiz(
    planet: Planet,
    profile_brief: str,
    rag: str,
    extra: str,
    quiz_types: Optional[List[str]] = None,
) -> tuple[str, str, dict]:
    """按教师勾选题型生成练习题；essay 与历史 case 等价。"""
    allowed = {"choice", "blank", "essay", "code", "case"}
    raw_types = [str(t).strip().lower() for t in (quiz_types or []) if str(t).strip()]
    selected: list[str] = []
    for t in raw_types:
        if t not in allowed:
            continue
        norm = "essay" if t == "case" else t
        if norm not in selected:
            selected.append(norm)
    if not selected:
        selected = ["choice", "blank", "essay", "code"]

    type_labels = {
        "choice": "选择题",
        "blank": "填空题",
        "essay": "大题/简答",
        "code": "程序题",
    }
    type_hint = "、".join(f"{t}({type_labels[t]})" for t in selected)
    per_type = 2 if len(selected) <= 2 else 1
    total = max(4, min(8, per_type * len(selected)))

    prompt = f"""你是 QuizAgent，为「{planet.name}」生成练习题。
只生成以下题型：{type_hint}（不要生成未列出的题型）。
每题字段：type(choice|blank|essay|code), question, options(仅选择题数组), answer, explanation, difficulty(easy|medium|hard)
每种勾选题型至少 {per_type} 题，合计约 {total} 题。
大题用 type=essay；程序题用 type=code。
画像：{profile_brief[:300]}
额外要求：{extra or '无'}
参考：{(rag or '')[:600]}"""

    fallback_bank = {
        "choice": {
            "type": "choice",
            "question": f"关于{planet.name}，下列说法正确的是？",
            "options": ["A. 选项一", "B. 选项二", "C. 选项三", "D. 选项四"],
            "answer": "A",
            "explanation": "结合定义判断。",
            "difficulty": "easy",
        },
        "blank": {
            "type": "blank",
            "question": f"请填写{planet.name}的核心关键词：____",
            "answer": (planet.name or "关键词")[:8],
            "explanation": "回顾讲义关键词。",
            "difficulty": "medium",
        },
        "essay": {
            "type": "essay",
            "question": f"请结合实例说明{planet.name}的核心思想与应用步骤。",
            "answer": "结合场景分析利弊与步骤。",
            "explanation": "注重概念与工程思维。",
            "difficulty": "hard",
        },
        "code": {
            "type": "code",
            "question": f"用伪代码描述{planet.name}的基本流程",
            "answer": "# 伪代码示例\nstep1()\nstep2()",
            "explanation": "关注步骤顺序。",
            "difficulty": "medium",
        },
    }
    questions: list[dict] = []
    for t in selected:
        for _ in range(per_type):
            questions.append(dict(fallback_bank[t]))

    if llm_available():
        raw = await llm_chat(
            [
                {
                    "role": "system",
                    "content": '只输出 JSON 对象 {"questions":[...]}，type 仅使用 choice/blank/essay/code。',
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            response_json=True,
        )
        if raw:
            parsed = extract_json(raw)
            if parsed and isinstance(parsed.get("questions"), list):
                cleaned: list[dict] = []
                for q in parsed["questions"]:
                    if not isinstance(q, dict):
                        continue
                    qt = str(q.get("type") or "").strip().lower()
                    if qt == "case":
                        qt = "essay"
                    if qt not in selected:
                        continue
                    q["type"] = qt
                    cleaned.append(q)
                if cleaned:
                    questions = cleaned

    return (
        f"{planet.name} 练习题",
        json.dumps({"questions": questions, "quiz_types": selected}, ensure_ascii=False),
        {"questions": questions, "quiz_types": selected},
    )


async def _agent_reading(planet: Planet, profile_brief: str, rag: str, extra: str) -> tuple[str, str, dict]:
    prompt = f"""你是 ReadAgent，为「{planet.name}」生成拓展阅读包 JSON：
{{"materials":[{{"title":"","summary":"","keywords":[],"difficulty":"medium"}}], "article":"深度阅读 Markdown 正文 400-600 字"}}
画像：{profile_brief[:300]}"""
    pack = {
        "materials": [
            {"title": f"{planet.name} 经典论文导读", "summary": "梳理领域发展脉络", "keywords": [planet.name, "综述"], "difficulty": "medium"},
            {"title": f"{planet.name} 实战博客精选", "summary": "工程实践中的典型用法", "keywords": ["实践", "案例"], "difficulty": "easy"},
        ],
        "article": f"## {planet.name} 深度阅读\n\n{planet.description}\n\n建议先回顾课堂讲义，再阅读拓展材料，关注概念之间的联系。",
    }
    if llm_available():
        raw = await llm_chat(
            [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
            temperature=0.6,
            response_json=True,
        )
        if raw:
            parsed = extract_json(raw)
            if isinstance(parsed, dict) and parsed.get("article"):
                pack = parsed
    return f"{planet.name} 拓展阅读", json.dumps(pack, ensure_ascii=False), pack


def _resolve_exact_cache_media_url(planet_slug: str) -> str | None:
    """仅精确匹配 slug 的预置片视为缓存加速，不做跨知识点回退。"""
    from pathlib import Path

    media_dir = Path(__file__).resolve().parents[1] / "static" / "media"
    candidate = media_dir / f"{planet_slug}.mp4"
    if candidate.is_file():
        return f"/static/media/{planet_slug}.mp4"
    return None


async def _build_media_slides(
    planet: Planet, profile_brief: str, rag: str
) -> tuple[list[dict], str, list[dict]]:
    citations: list[dict] = []
    try:
        citations = retrieve_citations(planet.name, k=6)
    except Exception:  # noqa: BLE001
        citations = []
    cite_hint = ""
    if citations:
        cite_hint = "\n可用引用（每幕 source_pages 须从中选取）：\n" + "\n".join(
            f"- {c.get('book', '')} p.{c.get('page', 0)}: {(c.get('snippet') or '')[:120]}"
            for c in citations[:6]
        )
    default = [
        {
            "title": f"引入：{planet.name}",
            "narration": f"今天我们来学习{planet.name}，它是理解后续内容的基础。",
            "bullet_points": ["学习目标", "知识定位"],
            "visual_hint": "星空背景 + 标题",
            "source_pages": (
                [{"book": citations[0]["book"], "page": citations[0]["page"], "snippet": citations[0].get("snippet", "")[:160]}]
                if citations
                else []
            ),
        },
        {
            "title": "核心概念",
            "narration": planet.description or "掌握核心定义与关键性质。",
            "bullet_points": ["定义", "关键性质"],
            "visual_hint": "概念卡片",
            "source_pages": (
                [{"book": citations[min(1, len(citations) - 1)]["book"], "page": citations[min(1, len(citations) - 1)]["page"], "snippet": citations[min(1, len(citations) - 1)].get("snippet", "")[:160]}]
                if citations
                else []
            ),
        },
        {
            "title": "例题演示",
            "narration": "通过一个简单例子建立直观认识。",
            "bullet_points": ["步骤 1", "步骤 2", "结论"],
            "visual_hint": "分步动画",
            "source_pages": (
                [{"book": citations[min(2, len(citations) - 1)]["book"], "page": citations[min(2, len(citations) - 1)]["page"], "snippet": citations[min(2, len(citations) - 1)].get("snippet", "")[:160]}]
                if citations
                else []
            ),
        },
        {
            "title": "总结",
            "narration": "回顾要点，完成自测巩固记忆。",
            "bullet_points": ["要点回顾", "自测建议"],
            "visual_hint": "总结页",
            "source_pages": (
                [{"book": citations[-1]["book"], "page": citations[-1]["page"], "snippet": citations[-1].get("snippet", "")[:160]}]
                if citations
                else []
            ),
        },
    ]
    if not llm_available():
        return default, "", citations
    prompt = f"""你是 MediaAgent，为「{planet.name}」生成分镜脚本 JSON：
{{"slides":[{{"title":"","narration":"","bullet_points":[],"visual_hint":"","source_pages":[{{"book":"","page":0,"snippet":""}}]}}]}}
要求：
- 4-6 幕，每幕 narration 40-70 字（将作为视频真实中文字幕，必须准确可读）
- 每幕必须含 source_pages（至少 1 条），book/page/snippet 须来自下方引用材料，禁止编造页码
- visual_hint：只用图形/图标/流程图描述画面，不要写「字幕」「文字」「标题字」
- 禁止娱乐化、禁止无关人物故事
画像：{profile_brief[:300]}
参考：{rag[:400]}
{cite_hint}
"""
    raw = await llm_chat(
        [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
        temperature=0.55,
        response_json=True,
    )
    if not raw:
        return default, "", citations
    parsed = extract_json(raw)
    if isinstance(parsed, dict) and isinstance(parsed.get("slides"), list) and parsed["slides"]:
        slides = parsed["slides"]
        for i, s in enumerate(slides):
            if isinstance(s, dict) and not s.get("source_pages") and citations:
                c = citations[i % len(citations)]
                s["source_pages"] = [{"book": c.get("book", ""), "page": c.get("page", 0), "snippet": (c.get("snippet") or "")[:160]}]
        return slides, "", citations
    return default, "", citations


async def _agent_media_gsap_fallback(
    planet: Planet,
    profile_brief: str,
    rag: str,
    *,
    reason: str = "",
    slides: list[dict] | None = None,
    citations: list[dict] | None = None,
) -> tuple[str, str, dict]:
    if slides is None or citations is None:
        built_slides, _, built_citations = await _build_media_slides(planet, profile_brief, rag)
        slides = slides or built_slides
        citations = citations if citations is not None else built_citations
    cache_url = _resolve_exact_cache_media_url(planet.slug)
    script = {
        "slides": slides,
        "provider": "cache_mp4" if cache_url else "deepseek_gsap",
        "media_url": cache_url or "",
        "knowledge_point_id": planet.slug,
        "source_refs": [f"planet:{planet.slug}"],
        "fallback_reason": reason,
        "degraded": True,
        "degraded_label": "动画预览（Seedance 不可用时的分镜降级）",
        "model": get_settings().deepseek_model if llm_available() else "",
        "fact_card": (rag or "")[:800],
        "citations": citations,
        "anti_hallucination": "分镜须对齐 fact_card / 校本引用，禁止编造公式与定义",
    }
    title = f"{planet.name} 教学短视频" if cache_url else f"{planet.name} 教学动画（预览降级）"
    return title, json.dumps(script, ensure_ascii=False), script


async def _agent_media(planet: Planet, profile_brief: str, rag: str, extra: str) -> tuple[str, str, dict]:
    """非流式入口：收集 stream_media_agent 最终结果。"""
    title, content, meta = "", "", {}
    async for item in stream_media_agent(planet, profile_brief, rag, extra):
        if isinstance(item, tuple):
            title, content, meta = item
    return title, content, meta


async def stream_media_agent(
    planet: Planet,
    profile_brief: str,
    rag: str,
    extra: str,
    *,
    session: AsyncSession | None = None,
    user: User | None = None,
) -> AsyncGenerator[ResourceEvent | tuple[str, str, dict], None]:
    """先 yield 过程事件，最后 yield (title, content, meta)。"""
    slides, _, citations = await _build_media_slides(planet, profile_brief, rag)
    seedance_prompt = build_teaching_seedance_prompt(planet.name, slides, extra=extra)
    fact_card = (rag or "")[:800]

    if seedance_available():
        prov = validate_slides_provenance(slides, citations)
        if not prov.get("ok"):
            if session is not None and user is not None:
                try:
                    from app.models.hallucination import HallucinationTicket

                    ticket = HallucinationTicket(
                        student_id=user.id,
                        teacher_id=getattr(user, "teacher_id", "") or "",
                        class_id=getattr(user, "class_id", "") or "",
                        challenge_id="",
                        planet_slug=planet.slug,
                        planet_name=planet.name,
                        knowledge_point_id=planet.slug,
                        cited_knowledge_point_id="media_provenance",
                        confidence=max(0.0, 1.0 - float(prov.get("conflict_ratio") or 1.0)),
                        reason="media_provenance",
                        question_preview=("；".join(prov.get("issues") or []))[:240],
                        status="pending",
                    )
                    session.add(ticket)
                    await session.commit()
                    prov = {**prov, "ticket_id": ticket.id}
                except Exception:  # noqa: BLE001
                    try:
                        await session.rollback()
                    except Exception:  # noqa: BLE001
                        pass
            yield await _emit(
                "MediaAgent",
                "media_blocked_no_provenance",
                f"分镜溯源未通过（冲突率 {prov.get('conflict_ratio', '?')}），跳过 Seedance：{'; '.join(prov.get('issues') or [])[:240]}",
                {"kind": "media", "provenance": prov},
                delay=0,
            )
            yield await _agent_media_gsap_fallback(
                planet,
                profile_brief,
                rag,
                reason="media_blocked_no_provenance",
                slides=slides,
                citations=citations,
            )
            return
        try:
            created = await create_video_task(seedance_prompt)
            task_id = created["id"]
            yield await _emit(
                "MediaAgent",
                "media_task_submitted",
                f"已提交 Seedance 视频任务：{task_id}（mode={created.get('mode', 't2v')}）",
                {"task_id": task_id, "kind": "media", "mode": created.get("mode")},
                delay=0,
            )

            from datetime import datetime, timezone

            settings = get_settings()
            interval = max(5, settings.ark_seedance_poll_interval)
            timeout = max(60, settings.ark_seedance_timeout)
            elapsed = 0

            while elapsed <= timeout:
                payload = await get_video_task(task_id)
                status = str(payload.get("status") or "").lower()
                yield await _emit(
                    "MediaAgent",
                    "media_polling",
                    f"Seedance 生成中… status={status}",
                    {"task_id": task_id, "status": status, "kind": "media"},
                    delay=0,
                )
                if status in ("succeeded", "success", "completed"):
                    remote = extract_video_url(payload)
                    if not remote:
                        raise RuntimeError(f"Seedance 成功但无 video_url: {payload}")
                    local = await download_video(remote, planet_slug=planet.slug)
                    duration = max(2, min(12, int(settings.ark_seedance_duration)))
                    composed = compose_seedance_prompt(
                        seedance_prompt,
                        duration=duration,
                        watermark=False,
                        resolution=settings.ark_seedance_resolution or "720p",
                        ratio=settings.ark_seedance_ratio or "16:9",
                    )
                    captions = build_caption_cues(
                        slides, duration_sec=float(duration), planet_name=planet.name
                    )
                    burned = burn_subtitles_into_mp4(local, captions)
                    if burned:
                        local = burned
                    script = {
                        "slides": slides,
                        "provider": "seedance_1_0_pro_fast",
                        "media_url": local,
                        "task_id": task_id,
                        "model": settings.ark_seedance_foundation_model or settings.ark_seedance_model,
                        "endpoint": settings.ark_seedance_model,
                        "mode": created.get("mode"),
                        "duration": duration,
                        "resolution": settings.ark_seedance_resolution,
                        "ratio": settings.ark_seedance_ratio,
                        "captions": captions,
                        "captions_burned": bool(burned),
                        "knowledge_point_id": planet.slug,
                        "source_refs": [f"planet:{planet.slug}"],
                        "prompt_brief": composed[:500],
                        "generated_at": datetime.now(timezone.utc).isoformat(),
                        "fact_card": fact_card,
                        "citations": citations,
                    }
                    yield f"{planet.name} 教学短视频", json.dumps(script, ensure_ascii=False), script
                    return
                if status in ("failed", "error", "cancelled", "canceled"):
                    raise RuntimeError(f"Seedance 任务失败: {payload.get('error') or payload}")
                await asyncio.sleep(interval)
                elapsed += interval
            raise TimeoutError(f"Seedance 轮询超时（{timeout}s）")
        except Exception as exc:  # noqa: BLE001
            yield await _emit(
                "MediaAgent",
                "media_fallback",
                f"Seedance 暂不可用，已降级为分镜动画预览（非故障）：{exc}",
                {"kind": "media", "error": str(exc)[:240], "degraded": True},
                delay=0,
            )
            yield await _agent_media_gsap_fallback(
                planet, profile_brief, rag, reason=str(exc)[:200], slides=slides, citations=citations
            )
            return

    yield await _agent_media_gsap_fallback(
        planet, profile_brief, rag, reason="未配置 ARK_API_KEY", slides=slides, citations=citations
    )


async def _agent_code(planet: Planet, profile_brief: str, rag: str, extra: str) -> tuple[str, str, dict]:
    prompt = f"""你是 CodeAgent，为「{planet.name}」生成代码实操案例 JSON：
{{"language":"python","code":"带注释代码","explanation":"运行说明","exercise":"课后练习任务"}}
画像：{profile_brief[:300]}"""
    case = {
        "language": "python",
        "code": f'# {planet.name} 实操示例\n\ndef demo():\n    """演示 {planet.name} 的核心思路"""\n    result = "Hello, SparkOrbit"\n    print(result)\n    return result\n\nif __name__ == "__main__":\n    demo()\n',
        "explanation": "在本地 Python 环境运行，观察输出并尝试修改参数。",
        "exercise": f"扩展 demo 函数，使其体现 {planet.name} 的一个典型应用场景。",
    }
    if llm_available():
        raw = await llm_chat(
            [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
            temperature=0.5,
            response_json=True,
        )
        if raw:
            parsed = extract_json(raw)
            if isinstance(parsed, dict) and parsed.get("code"):
                case = parsed
    return f"{planet.name} 代码实操", json.dumps(case, ensure_ascii=False), case


async def _agent_deck(
    planet: Planet, profile_brief: str, rag: str, extra: str, theme_id: str = "orbit"
) -> tuple[str, str, dict]:
    """教学课件：分镜幻灯片 + pptx 导出（旁白进备注）。"""
    from app.services.deck_export import export_deck_pptx
    from app.services.deck_themes import resolve_theme

    slides, _, citations = await _build_media_slides(planet, profile_brief, rag)
    # 课件场景加强要点条数
    for s in slides:
        if isinstance(s, dict) and not s.get("bullet_points"):
            narr = str(s.get("narration") or "")
            s["bullet_points"] = [p.strip() for p in narr.replace("。", "。|").split("|") if p.strip()][:4] or ["要点"]

    try:
        from app.services.media_provenance import validate_slides_provenance

        prov = validate_slides_provenance(slides, citations)
        if not prov.get("ok"):
            import logging

            logging.getLogger(__name__).warning("deck provenance weak: %s", prov.get("issues"))
    except Exception:  # noqa: BLE001
        pass

    theme = resolve_theme(theme_id)
    title = f"{planet.name} · 教学课件"
    pptx_url = ""
    try:
        pptx_url = export_deck_pptx(
            title=title, slides=slides, planet_slug=planet.slug, theme_id=theme["id"]
        )
    except Exception as exc:  # noqa: BLE001
        pptx_url = ""
        err = str(exc)[:200]
    else:
        err = ""

    payload = {
        "title": title,
        "slides": slides,
        "pptx_url": pptx_url,
        "citations": citations,
        "export_error": err,
        "deck_template": theme["id"],
    }
    meta = {
        "kind": "deck",
        "provider": "deck_pptx",
        "pptx_url": pptx_url,
        "slide_count": len(slides),
        "citations": citations,
        "export_error": err,
        "deck_template": theme["id"],
    }
    if extra:
        meta["extra_requirements"] = extra[:200]
    return title, json.dumps(payload, ensure_ascii=False), meta


AGENT_FUNCS = {
    "doc": _agent_doc,
    "mindmap": _agent_mindmap,
    "quiz": _agent_quiz,
    "reading": _agent_reading,
    "media": _agent_media,
    "deck": _agent_deck,
    "code": _agent_code,
}


async def _produce_one_kind(
    *,
    session: AsyncSession,
    user: User,
    planet: Planet,
    kind: ResourceKind,
    brief: str,
    rag: str,
    extra_requirements: str,
    quiz_types: Optional[List[str]],
    deck_template: str = "orbit",
) -> tuple[list[ResourceEvent], bool]:
    """生成单类资源，返回 SSE 事件列表与是否成功。"""
    role, label = AGENT_LABELS.get(kind, ("Coordinator", kind))
    events: list[ResourceEvent] = []
    title, content, meta = "", "", {}
    try:
        attempts = 0
        while attempts < 2:
            attempts += 1
            if kind == "doc" and llm_available() and attempts == 1:
                prompt = f"你是 DocAgent，为「{planet.name}」写一段 200 字以内的讲解开篇（Markdown）。画像：{brief[:200]}"
                async for token in llm_chat_stream(
                    [{"role": "system", "content": "你是讲解文档 Agent"}, {"role": "user", "content": prompt}],
                    temperature=0.6,
                    user_id=str(getattr(user, "id", "") or ""),
                    endpoint="resource_doc",
                ):
                    events.append(await _emit(role, "token", token, {"kind": kind}, delay=0))

            if kind == "media":
                async for item in stream_media_agent(
                    planet, brief, rag, extra_requirements, session=session, user=user
                ):
                    if isinstance(item, tuple):
                        title, content, meta = item
                    else:
                        events.append(item)
            elif kind == "quiz":
                title, content, meta = await _agent_quiz(
                    planet, brief, rag, extra_requirements, quiz_types=quiz_types
                )
            elif kind == "deck":
                title, content, meta = await _agent_deck(
                    planet, brief, rag, extra_requirements, theme_id=deck_template
                )
            else:
                fn = AGENT_FUNCS[kind]
                title, content, meta = await fn(planet, brief, rag, extra_requirements)

            quality = await score_resource(
                kind=kind,
                title=title,
                content=content,
                planet_name=planet.name,
                planet_slug=planet.slug,
                profile_brief=brief,
            )
            profile_reason = ""
            try:
                from app.services.profile_refresh import build_profile_reason

                latest_prof = await get_latest_profile(session, user_id=user.id) if user else None
                profile_reason = build_profile_reason(latest_prof)
            except Exception:
                profile_reason = ""
            meta = {**(meta or {}), "quality": quality}
            if profile_reason:
                meta["profile_reason"] = profile_reason
            if quality.get("should_retry") and attempts < 2 and kind != "media":
                events.append(
                    await _emit(
                        role,
                        "quality_retry",
                        f"{label} 质量偏低（{quality_summary(quality)}），自动重生成…",
                        {"kind": kind, "quality": quality},
                    )
                )
                continue
            if quality.get("should_retry") and kind == "media" and attempts < 2 and seedance_available():
                events.append(
                    await _emit(
                        role,
                        "quality_retry",
                        f"教学视频质量偏低（{quality_summary(quality)}），重试 Seedance…",
                        {"kind": kind, "quality": quality},
                    )
                )
                continue
            break

        row = await _save_resource(session, user.id, planet, kind, title, content, meta)
        done_msg = f"{label} 已完成：{title} · {quality_summary(meta.get('quality'))}"
        if kind == "deck" and not (meta or {}).get("pptx_url"):
            export_err = str((meta or {}).get("export_error") or "未知原因")
            done_msg += f"（PPT 导出失败：{export_err[:80]}）"
        events.append(
            await _emit(
                role,
                "resource_done",
                done_msg,
                {
                    "kind": kind,
                    "resource_id": row.id,
                    "title": title,
                    "content": content,
                    "meta": meta,
                },
            )
        )
        return events, True
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).exception("resource agent %s failed: %s", kind, exc)
        try:
            fb_title = title or f"{planet.name} {label}"
            fb_content = content or f"# {planet.name}\n\n生成失败，请重试。\n\n错误：{exc}"
            row = await _save_resource(
                session,
                user.id,
                planet,
                kind,
                fb_title,
                fb_content,
                {**(meta or {}), "error": str(exc), "fallback": True},
            )
            events.append(
                await _emit(
                    role,
                    "resource_done",
                    f"{label} 已降级保存：{fb_title}",
                    {
                        "kind": kind,
                        "resource_id": row.id,
                        "title": fb_title,
                        "content": fb_content,
                        "meta": {"error": str(exc), "fallback": True},
                    },
                )
            )
            return events, True
        except Exception as save_exc:  # noqa: BLE001
            events.append(await _emit(role, "error", f"{label} 失败：{save_exc}", {"kind": kind}))
            return events, False


async def run_resource_generation(
    session: AsyncSession,
    user: User,
    planet_slug: str,
    kinds: List[ResourceKind],
    extra_requirements: str = "",
    quiz_types: Optional[List[str]] = None,
    run_id: str = "",
    deck_template: str = "orbit",
) -> AsyncGenerator[ResourceEvent, None]:
    """Coordinator workflow：按 C2 三组 DAG 并行/依赖执行，并写入 AgentStep。"""
    from app.services import agent_trace

    planet = await _get_planet(session, planet_slug)
    if planet is None:
        yield await _emit("System", "error", f"未找到知识点：{planet_slug}")
        return

    profile = await get_latest_profile(session, user_id=user.id)
    brief = _profile_brief(profile)
    rag = build_rag_context(planet.name) or ""
    # 画像只影响组内展示顺序提示；DAG 结构以 C2 为准
    preferred = _sort_kinds_by_profile(kinds, profile)
    plan = agent_trace.build_resource_workflow_plan(list(kinds))
    # 组内按画像偏好重排
    rank = {k: i for i, k in enumerate(preferred)}
    plan["parallel_groups"] = [sorted(g, key=lambda k: rank.get(k, 99)) for g in plan["parallel_groups"]]
    plan["order"] = [k for g in plan["parallel_groups"] for k in g]
    kind_to_step = {s["payload"]["kind"]: int(s["step_index"]) for s in plan["steps"]}

    if run_id:
        update_resource_run_status(run_id, "running", planet_slug=planet_slug, kinds=list(kinds))
        try:
            await agent_trace.start_agent_run(
                session,
                run_id=run_id,
                user=user,
                scene="resource",
                mode="workflow",
                topic=planet.name,
                graph_plan=plan,
            )
            await agent_trace.ensure_steps(session, run_id, plan["steps"])
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("agent_trace start failed for resource %s: %s", run_id, exc)

    degraded = not llm_available()
    yield await _emit(
        "Coordinator",
        "start",
        f"已接收任务：为「{planet.name}」按 workflow DAG 生成 {len(plan['order'])} 类资源"
        + (f"（并行组 {len(plan['parallel_groups'])}）")
        + (" · 演示降级（未配置 LLM）" if degraded else ""),
        {
            "planet_slug": planet.slug,
            "kinds": plan["order"],
            "mode": "workflow",
            "graph_plan": plan,
            "run_id": run_id,
            "degraded": degraded,
        },
    )

    any_fail = False
    for group in plan["parallel_groups"]:
        group_kinds = [k for k in group if k in AGENT_FUNCS or k == "media"]
        if not group_kinds:
            continue
        for kind in group_kinds:
            role, label = AGENT_LABELS.get(kind, ("Coordinator", kind))  # type: ignore[arg-type]
            step_index = kind_to_step.get(kind, 0)
            if run_id:
                try:
                    await agent_trace.mark_step_running(
                        session,
                        run_id,
                        step_index=step_index,
                        agent_role=str(role),
                        parallel_group=next(
                            (s["parallel_group"] for s in plan["steps"] if s["payload"].get("kind") == kind),
                            "",
                        ),
                        summary=f"{label} 运行中",
                        payload={"kind": kind},
                    )
                except Exception as exc:  # noqa: BLE001
                    import logging

                    logging.getLogger(__name__).exception(
                        "agent_trace mark_step_running failed run=%s kind=%s: %s", run_id, kind, exc
                    )

        # 同组真正并行：每任务独立 AsyncSession，避免共享 session 并发写
        from app.db.session import AsyncSessionLocal

        planet_id = planet.id
        user_id = user.id

        async def _job(kind: ResourceKind) -> tuple[ResourceKind, list[ResourceEvent], bool]:
            async with AsyncSessionLocal() as own_session:
                own_planet = await own_session.get(Planet, planet_id)
                own_user = await own_session.get(User, user_id)
                if own_planet is None or own_user is None:
                    role, label = AGENT_LABELS.get(kind, ("Coordinator", kind))  # type: ignore[arg-type]
                    return kind, [await _emit(role, "error", f"{label} 失败：会话上下文丢失", {"kind": kind})], False
                events, ok = await _produce_one_kind(
                    session=own_session,
                    user=own_user,
                    planet=own_planet,
                    kind=kind,
                    brief=brief,
                    rag=rag,
                    extra_requirements=extra_requirements,
                    quiz_types=quiz_types,
                    deck_template=deck_template,
                )
                return kind, events, ok

        results = await asyncio.gather(*[_job(k) for k in group_kinds], return_exceptions=True)
        for item in results:
            if isinstance(item, Exception):
                any_fail = True
                yield await _emit("System", "error", f"并行组任务异常：{item}", {})
                continue
            kind, events, ok = item
            if not ok:
                any_fail = True
            for ev in events:
                yield ev
            step_index = kind_to_step.get(kind, 0)
            role, label = AGENT_LABELS.get(kind, ("Coordinator", kind))  # type: ignore[arg-type]
            if run_id:
                try:
                    await agent_trace.mark_step_done(
                        session,
                        run_id,
                        step_index=step_index,
                        summary=f"{label} {'完成' if ok else '失败'}",
                        payload={"kind": kind, "ok": ok},
                        ok=ok,
                    )
                except Exception as exc:  # noqa: BLE001
                    import logging

                    logging.getLogger(__name__).exception(
                        "agent_trace mark_step_done failed run=%s kind=%s: %s", run_id, kind, exc
                    )

    if run_id:
        update_resource_run_status(
            run_id,
            "failed" if any_fail else "completed",
            planet_slug=planet.slug,
            ok=not any_fail,
        )
        try:
            await agent_trace.finish_agent_run(
                session,
                run_id,
                status="failed" if any_fail else "completed",
            )
        except Exception as exc:  # noqa: BLE001
            import logging

            logging.getLogger(__name__).exception("agent_trace finish failed for resource %s: %s", run_id, exc)

    yield await _emit(
        "Coordinator",
        "complete",
        "全部资源生成完成" if not any_fail else "资源生成结束（部分失败）",
        {"planet_slug": planet.slug, "mode": "workflow", "ok": not any_fail, "degraded": not llm_available()},
    )


async def list_user_resources(
    session: AsyncSession,
    user_id: str,
    *,
    planet_slug: str = "",
    kind: str = "",
) -> list[dict]:
    stmt = select(GeneratedResource).where(GeneratedResource.user_id == user_id).order_by(GeneratedResource.created_at.desc())
    if planet_slug:
        stmt = stmt.where(GeneratedResource.planet_slug == planet_slug)
    if kind:
        stmt = stmt.where(GeneratedResource.kind == kind)
    rows = (await session.execute(stmt.limit(100))).scalars().all()
    return [
        {
            "id": r.id,
            "planet_slug": r.planet_slug,
            "planet_name": r.planet_name,
            "kind": r.kind,
            "title": r.title,
            "content": r.content,
            "meta_json": r.meta_json or {},
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


async def get_resource(session: AsyncSession, user_id: str, resource_id: str) -> Optional[dict]:
    row = (
        await session.execute(
            select(GeneratedResource).where(GeneratedResource.id == resource_id, GeneratedResource.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "planet_slug": row.planet_slug,
        "planet_name": row.planet_name,
        "kind": row.kind,
        "title": row.title,
        "content": row.content,
        "meta_json": row.meta_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }
