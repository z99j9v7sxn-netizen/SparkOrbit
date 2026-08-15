"""数字人讲解编排：RAG 文案 → 讯飞视频 → 本地资产。"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.galaxy import Galaxy, Planet
from app.models.star_asset import StarAsset
from app.models.user import User
from app.services import rag
from app.services import starlib as starlib_svc
from app.services import xf_digital_human as xf_dh
from pathlib import Path as FsPath

logger = logging.getLogger(__name__)

# 进程内任务状态（与 resource_agents._RUNS 同模式）
_TASKS: dict[str, dict[str, Any]] = {}
# 错题 / 行星分镜讲稿轻量缓存（不做 StarAsset MP4）
_MISTAKE_EXPLAIN_CACHE: dict[str, dict[str, Any]] = {}
_PLANET_EXPLAIN_CACHE: dict[str, dict[str, Any]] = {}
_BACKEND_ROOT = FsPath(__file__).resolve().parents[2]
# 讯飞视频大模型并发=1：仅遗留 videoGenerate 路径使用
_INFLIGHT_LOCAL_ID: str | None = None
_INFLIGHT_LOCK = asyncio.Lock()


def digital_human_available() -> bool:
    """讯飞数字人视频大模型是否已配置可用。"""
    return xf_dh.xf_digital_human_available()


def get_task(task_id: str) -> Optional[dict[str, Any]]:
    return _TASKS.get(task_id)


def _local_path_from_url(file_url: str) -> FsPath | None:
    url = (file_url or "").strip()
    if url.startswith("/static/media/"):
        return _BACKEND_ROOT / "app" / "static" / "media" / url[len("/static/media/") :]
    if url.startswith("/static/uploads/"):
        return _BACKEND_ROOT / "uploads" / url[len("/static/uploads/") :]
    return None


def _file_url_exists(file_url: str) -> bool:
    path = _local_path_from_url(file_url)
    return bool(path and path.is_file() and path.stat().st_size > 0)


def _asset_to_saved_task(asset: StarAsset, *, planet_name: str = "") -> dict[str, Any]:
    meta = asset.meta_json if isinstance(asset.meta_json, dict) else {}
    citations = meta.get("citations") if isinstance(meta.get("citations"), list) else []
    script = str(meta.get("script") or asset.description or "")
    return {
        "task_id": f"saved_{asset.id}",
        "status": "succeeded",
        "fallback": False,
        "error": "",
        "message": "已加载本行星缓存的数字人讲解视频",
        "planet_slug": asset.planet_slug or "",
        "galaxy_slug": asset.galaxy_slug or "",
        "prompt": str(meta.get("prompt") or planet_name or ""),
        "script": script,
        "citations": citations,
        "video_url": asset.file_url,
        "remote_video_url": meta.get("remote_video_url"),
        "cover_image": meta.get("cover_image"),
        "audio_url": meta.get("audio_url"),
        "xf_task_id": meta.get("xf_task_id"),
        "xf_task_status": "4",
        "asset": starlib_svc._row_out(asset) if hasattr(starlib_svc, "_row_out") else {"id": asset.id, "file_url": asset.file_url, "title": asset.title},
        "provider": meta.get("provider") or "xf_digital_human",
        "cached": True,
        "mode": str(meta.get("mode") or ("mistake" if meta.get("source") == "digital_tutor_mistake" else "planet")),
        "mistake_id": str(meta.get("mistake_id") or ""),
    }


async def find_saved_for_planet(
    session: AsyncSession,
    *,
    planet_slug: str,
) -> Optional[dict[str, Any]]:
    """优先返回行星分镜缓存；若无则回退旧版 MP4 资产（兼容）。"""
    slug = (planet_slug or "").strip()
    if not slug:
        return None
    cached = _PLANET_EXPLAIN_CACHE.get(slug)
    if cached and cached.get("slides"):
        out = dict(cached)
        out["cached"] = True
        out["message"] = out.get("message") or "已加载该行星的分镜讲稿缓存"
        return _public_task(out)
    rows = (
        await session.execute(
            select(StarAsset)
            .where(
                StarAsset.planet_slug == slug,
                StarAsset.asset_type == "video_local",
                StarAsset.status == "ready",
            )
            .order_by(StarAsset.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    for row in rows:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        if str(meta.get("source") or "") != "digital_tutor":
            continue
        if not row.file_url or not _file_url_exists(row.file_url):
            continue
        planet = (
            await session.execute(select(Planet).where(Planet.slug == slug))
        ).scalar_one_or_none()
        return _asset_to_saved_task(row, planet_name=planet.name if planet else slug)
    return None


async def get_saved(
    session: AsyncSession,
    *,
    planet_slug: str = "",
    mistake_id: str = "",
) -> dict[str, Any]:
    mid = (mistake_id or "").strip()
    if mid:
        saved = await find_saved_for_mistake(session, mistake_id=mid)
        if saved:
            return saved
        return {
            "task_id": "",
            "status": "empty",
            "fallback": False,
            "error": "",
            "message": "该错题尚无分镜讲稿缓存",
            "planet_slug": "",
            "galaxy_slug": "",
            "prompt": "",
            "script": "",
            "summary": "",
            "slides": [],
            "citations": [],
            "video_url": None,
            "cached": False,
            "provider": "mistake_gsap",
            "mode": "mistake",
            "mistake_id": mid,
        }
    saved = await find_saved_for_planet(session, planet_slug=planet_slug)
    if saved:
        return saved
    return {
        "task_id": "",
        "status": "empty",
        "fallback": False,
        "error": "",
        "message": "本行星尚无已保存的数字人视频",
        "planet_slug": planet_slug,
        "galaxy_slug": "",
        "prompt": "",
        "script": "",
        "citations": [],
        "video_url": None,
        "cached": False,
        "provider": "xf_digital_human",
        "mode": "planet",
        "mistake_id": "",
    }


def _xf_status_message(status: Any) -> str:
    """讯飞 task_status：1 已创建 / 2 处理中 / 3 待回调 / 4 完成。"""
    code = str(status or "").strip()
    mapping = {
        "1": "讯飞已接单，云端渲染队列中（通常 1～5 分钟，忙时更久）。可先看下方文案；成功后按本题缓存。",
        "2": "讯飞正在渲染（通常 1～5 分钟）。可先看下方文案；成功后下次将直接播放。",
        "3": "渲染完成，正在拉取视频…",
        "4": "渲染完成，正在下载入库…",
    }
    if code in mapping:
        return mapping[code]
    return f"数字人生成中（讯飞状态 {code or '?'}）…"


def _public_task(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": row.get("task_id"),
        "status": row.get("status"),
        "fallback": bool(row.get("fallback")),
        "error": row.get("error") or "",
        "message": row.get("message") or "",
        "planet_slug": row.get("planet_slug") or "",
        "galaxy_slug": row.get("galaxy_slug") or "",
        "prompt": row.get("prompt") or "",
        "script": row.get("script") or "",
        "summary": row.get("summary") or "",
        "slides": row.get("slides") or [],
        "citations": row.get("citations") or [],
        "video_url": row.get("video_url"),
        "remote_video_url": row.get("remote_video_url"),
        "cover_image": row.get("cover_image"),
        "audio_url": row.get("audio_url"),
        "xf_task_id": row.get("xf_task_id"),
        "xf_task_status": row.get("xf_task_status") or "",
        "asset": row.get("asset"),
        "provider": row.get("provider") or "xf_digital_human",
        "cached": bool(row.get("cached")),
        "mode": row.get("mode") or "planet",
        "mistake_id": row.get("mistake_id") or "",
    }


def build_script_bundle(
    *,
    planet_name: str,
    planet_desc: str,
    prompt: str,
    galaxy_slug: str = "",
    word_count: int = 120,
) -> dict[str, Any]:
    """基于 RAG citation 组装数字人播报 prompt 与可展示文案。"""
    topic = (prompt or "").strip() or f"讲解知识点「{planet_name}」"
    citations = rag.retrieve_citations(topic, galaxy_slug=galaxy_slug or None, k=4)
    if not citations and planet_desc:
        citations = [
            {
                "snippet": planet_desc[:280],
                "citation": f"《行星简介·{planet_name}》",
                "book": planet_name,
                "page": 0,
                "score": 0.5,
                "source": "planet_desc",
                "text": planet_desc[:400],
            }
        ]
    rag_ctx = rag.build_rag_context(topic, galaxy_slug=galaxy_slug or None)

    wc = max(50, min(300, int(word_count or 120)))
    # 讯飞约束：parameter.avatar.prompt 长度必须 ≤ 300（code 10163）
    # 只传短讲题；详细引用留给面板展示，不塞进 API prompt
    desc_brief = _brief_text(planet_desc, 80)
    cite_brief = ""
    if citations:
        first = citations[0]
        cite_brief = _brief_text(
            f"{first.get('citation') or '校本'}：{first.get('snippet') or ''}",
            60,
        )
    xf_prompt = (
        f"用约{wc}字讲解「{planet_name}」。"
        f"要点：{desc_brief or topic}。"
    )
    if cite_brief:
        xf_prompt += f"依据{cite_brief}"
    xf_prompt = _clamp_xf_prompt(xf_prompt)

    spoken = (
        f"同学们好，今天我们来讲「{planet_name}」。"
        f"{desc_brief or '这是本课程的核心知识点。'}"
    )
    if citations:
        first = citations[0]
        spoken += f"依据{first.get('citation') or '校本资料'}，可以这样理解："
        spoken += str(first.get("snippet") or "")[:120]
    spoken += "请结合练习巩固，有疑问随时提问。"

    return {
        "xf_prompt": xf_prompt,
        "script": spoken,
        "citations": citations,
        "rag_context": rag_ctx,
        "topic": topic,
        "word_count": wc,
    }


_XF_PROMPT_MAX = 300


def _brief_text(text: str, limit: int) -> str:
    """压缩空白并截断；顺带丢掉 seed 元数据行，避免污染讲题。"""
    skip_prefixes = ("知识点ID", "知识点id", "名称:", "名称：", "所属星系", "难度:", "难度：", "标签:", "标签：")
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(line.startswith(p) for p in skip_prefixes):
            continue
        lines.append(line)
    t = " ".join(lines) if lines else " ".join((text or "").split())
    if len(t) <= limit:
        return t
    return t[: max(0, limit - 1)].rstrip() + "…"


def _clamp_xf_prompt(text: str) -> str:
    t = " ".join((text or "").strip().split())
    if not t:
        return "请简明讲解本知识点要点。"
    if len(t) <= _XF_PROMPT_MAX:
        return t
    return t[: _XF_PROMPT_MAX - 1].rstrip() + "…"


async def _resolve_planet(
    session: AsyncSession, planet_slug: str
) -> tuple[Planet, str]:
    planet = (
        await session.execute(select(Planet).where(Planet.slug == planet_slug))
    ).scalar_one_or_none()
    if planet is None:
        raise ValueError(f"行星不存在: {planet_slug}")
    galaxy = (
        await session.execute(select(Galaxy).where(Galaxy.id == planet.galaxy_id))
    ).scalar_one_or_none()
    galaxy_slug = galaxy.slug if galaxy else ""
    return planet, galaxy_slug


def build_mistake_prompt(
    *,
    question: str,
    student_answer: str,
    correct_answer: str,
    note: str = "",
    subject: str = "",
) -> str:
    """错题短讲题（历史 videoGenerate 用）；现错题模式改走 analyze_mistake_explain。"""
    q = _brief_text(question, 90)
    sa = _brief_text(student_answer or "未作答", 40)
    ca = _brief_text(correct_answer or "见解析", 40)
    hint = _brief_text(note or subject or "", 50)
    raw = (
        f"用约60字讲清这道错题：题干「{q}」；学生答「{sa}」；正解「{ca}」。"
        f"指出错因并给出记忆点。"
    )
    if hint:
        raw += f"补充：{hint}"
    return _clamp_xf_prompt(raw)


def _normalize_mistake_slides(raw_slides: Any) -> list[dict[str, Any]]:
    """对齐资源工坊分镜字段：title / narration / bullet_points / visual_hint。"""
    out: list[dict[str, Any]] = []
    if not isinstance(raw_slides, list):
        return out
    for item in raw_slides[:5]:
        if not isinstance(item, dict):
            continue
        bullets = item.get("bullet_points") or item.get("bullets") or []
        if isinstance(bullets, str):
            bullets = [bullets]
        if not isinstance(bullets, list):
            bullets = []
        clean_bullets = [str(b).strip() for b in bullets if str(b).strip()][:5]
        title = str(item.get("title") or "").strip() or f"第{len(out) + 1}幕"
        narration = str(item.get("narration") or item.get("script") or "").strip()
        if not narration:
            narration = "；".join(clean_bullets) if clean_bullets else title
        visual = str(item.get("visual_hint") or item.get("visual") or "").strip()
        out.append(
            {
                "title": title[:40],
                "narration": narration[:200],
                "bullet_points": clean_bullets,
                "visual_hint": visual[:80],
            }
        )
    return out


def _fallback_mistake_slides(
    *,
    question: str,
    student_answer: str,
    correct_answer: str,
    note: str = "",
) -> list[dict[str, Any]]:
    q = _brief_text(question, 60)
    sa = _brief_text(student_answer or "未作答", 36)
    ca = _brief_text(correct_answer or "见解析", 36)
    hint = _brief_text(note, 50)
    return [
        {
            "title": "审题要点",
            "narration": f"先抓住题干关键信息：{q}。",
            "bullet_points": ["读清条件与所求", "标出易混关键词"],
            "visual_hint": "题干高亮卡片",
        },
        {
            "title": "对错对比",
            "narration": f"你答了「{sa}」，正解是「{ca}」。对比两者差异就能定位错因。",
            "bullet_points": [f"作答：{sa}", f"正解：{ca}"],
            "visual_hint": "左右对照板",
        },
        {
            "title": "错因拆解",
            "narration": hint or "常见错因是概念混淆或步骤遗漏，下次先自检再下笔。",
            "bullet_points": ["对照正解找断点", "用一句话复述正确思路"],
            "visual_hint": "错因标签列表",
        },
        {
            "title": "记忆点",
            "narration": "把正解思路压成一句口诀，做错同类题时先回忆这句。",
            "bullet_points": ["一句话口诀", "同类题立刻自检"],
            "visual_hint": "记忆星标",
        },
    ]


async def analyze_mistake_explain(
    *,
    question: str,
    student_answer: str = "",
    correct_answer: str = "",
    note: str = "",
    subject: str = "",
    user_id: str = "",
) -> dict[str, Any]:
    """DeepSeek 分析错题 → slides + 汇总讲稿（不走讯飞 videoGenerate）。"""
    from app.services.llm import extract_json, llm_available, llm_chat

    q = (question or "").strip()
    sa = (student_answer or "").strip() or "未作答"
    ca = (correct_answer or "").strip() or "见解析"
    hint = (note or "").strip()
    subj = (subject or "").strip()

    slides = _fallback_mistake_slides(
        question=q, student_answer=sa, correct_answer=ca, note=hint
    )
    summary = "对照作答与正解，抓住错因与记忆点即可。"
    used_llm = False

    if llm_available() and q:
        prompt = f"""你是错题讲解教练。根据错题生成分镜 JSON（供前端 GSAP 切幕 + 虚拟人朗读）：
{{"summary":"总述一句","slides":[{{"title":"","narration":"","bullet_points":[],"visual_hint":""}}]}}
要求：
- slides 3～5 幕，建议结构：审题 → 对错对比 → 错因 → 正解思路 → 记忆点
- 每幕 narration 40～90 字，口语化，可直接给虚拟人朗读
- bullet_points 2～4 条短要点；visual_hint 用图形/对照/流程图描述画面（不要写「字幕」）
- 禁止娱乐化、禁止无关故事
学科：{subj or "未指定"}
题干：{q[:500]}
学生作答：{sa[:200]}
正解：{ca[:200]}
备注：{hint[:200] or "无"}
"""
        raw = await llm_chat(
            [
                {"role": "system", "content": "只输出 JSON，不要 Markdown。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.45,
            response_json=True,
            timeout=75.0,
            user_id=user_id,
            endpoint="mistake_explain",
        )
        parsed = extract_json(raw or "")
        if isinstance(parsed, dict):
            normalized = _normalize_mistake_slides(parsed.get("slides"))
            if len(normalized) >= 3:
                slides = normalized
                used_llm = True
            if str(parsed.get("summary") or "").strip():
                summary = str(parsed.get("summary")).strip()[:120]

    script_parts = [str(s.get("narration") or "").strip() for s in slides if s.get("narration")]
    script = " ".join(script_parts).strip() or summary
    return {
        "slides": slides,
        "summary": summary,
        "script": script,
        "provider": "mistake_gsap",
        "used_llm": used_llm,
    }


async def find_saved_for_mistake(
    session: AsyncSession,
    *,
    mistake_id: str,
) -> Optional[dict[str, Any]]:
    mid = (mistake_id or "").strip()
    if not mid:
        return None
    cached = _MISTAKE_EXPLAIN_CACHE.get(mid)
    if cached and cached.get("slides"):
        out = dict(cached)
        out["cached"] = True
        out["message"] = out.get("message") or "已加载该错题的分镜讲稿缓存"
        return _public_task(out)
    # 兼容历史：仍可返回旧版 video_local 缓存（若存在）
    rows = (
        await session.execute(
            select(StarAsset)
            .where(StarAsset.asset_type == "video_local", StarAsset.status == "ready")
            .order_by(StarAsset.created_at.desc())
            .limit(40)
        )
    ).scalars().all()
    for row in rows:
        meta = row.meta_json if isinstance(row.meta_json, dict) else {}
        if str(meta.get("source") or "") != "digital_tutor_mistake":
            continue
        if str(meta.get("mistake_id") or "") != mid:
            continue
        if not row.file_url or not _file_url_exists(row.file_url):
            continue
        out = _asset_to_saved_task(row, planet_name=str(meta.get("title") or "错题讲解"))
        out["message"] = "已加载该错题的数字人讲解缓存"
        out["mistake_id"] = mid
        return out
    return None


def _fallback_planet_slides(
    *,
    planet_name: str,
    script: str,
    citations: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """按讲稿切幕：引入 → 要点 → 依据 → 小结。"""
    name = (planet_name or "本知识点").strip() or "本知识点"
    spoken = " ".join((script or "").split()).strip()
    cite0 = ""
    if citations:
        first = citations[0]
        cite0 = _brief_text(
            f"{first.get('citation') or '校本'}：{first.get('snippet') or first.get('text') or ''}",
            80,
        )
    # 尽量按句号切段
    parts = [p.strip() for p in spoken.replace("！", "。").split("。") if p.strip()]
    intro = parts[0] if parts else f"今天我们来讲「{name}」。"
    body = "。".join(parts[1:3]).strip() if len(parts) > 1 else (spoken[len(intro) :].strip() or spoken)
    if body and not body.endswith(("。", "！", "？")):
        body += "。"
    closing = parts[-1] if len(parts) > 3 else "请结合练习巩固，有疑问随时提问。"
    slides = [
        {
            "title": f"认识「{name}」",
            "narration": intro if intro.endswith(("。", "！", "？")) else intro + "。",
            "bullet_points": [f"主题：{name}", "先建立整体印象"],
            "visual_hint": "知识点标题卡",
        },
        {
            "title": "核心要点",
            "narration": body or f"「{name}」是本课需要掌握的核心概念，抓住定义与适用场景。",
            "bullet_points": ["抓住定义", "联系应用场景"],
            "visual_hint": "要点列表",
        },
    ]
    if cite0:
        slides.append(
            {
                "title": "校本依据",
                "narration": f"依据资料可以这样理解：{cite0}",
                "bullet_points": ["对照教材表述", "记住出处便于复习"],
                "visual_hint": "引用卡片",
            }
        )
    slides.append(
        {
            "title": "小结与练习",
            "narration": closing if closing.endswith(("。", "！", "？")) else closing + "。",
            "bullet_points": ["回顾一句定义", "立刻做一道巩固题"],
            "visual_hint": "记忆星标",
        }
    )
    return slides[:5]


async def analyze_planet_explain(
    *,
    planet_name: str,
    planet_desc: str = "",
    prompt: str = "",
    galaxy_slug: str = "",
    user_id: str = "",
    word_count: int = 120,
) -> dict[str, Any]:
    """行星通识：RAG 讲稿 + DeepSeek 分镜（不走讯飞 videoGenerate）。"""
    from app.services.llm import extract_json, llm_available, llm_chat

    bundle = build_script_bundle(
        planet_name=planet_name,
        planet_desc=planet_desc,
        prompt=prompt,
        galaxy_slug=galaxy_slug,
        word_count=word_count,
    )
    name = (planet_name or "").strip() or "本知识点"
    topic = str(bundle.get("topic") or "")
    script = str(bundle.get("script") or "")
    citations = bundle.get("citations") if isinstance(bundle.get("citations"), list) else []
    rag_ctx = _brief_text(str(bundle.get("rag_context") or ""), 400)

    slides = _fallback_planet_slides(planet_name=name, script=script, citations=citations)
    summary = f"通识讲解「{name}」。"
    used_llm = False

    if llm_available():
        cite_lines = []
        for c in citations[:3]:
            if not isinstance(c, dict):
                continue
            cite_lines.append(
                f"- {c.get('citation') or c.get('book') or '校本'}：{_brief_text(str(c.get('snippet') or c.get('text') or ''), 80)}"
            )
        cite_block = "\n".join(cite_lines) or "（无额外引用）"
        llm_prompt = f"""你是课程通识讲解教练。根据知识点生成分镜 JSON（供前端 GSAP 切幕 + 实时虚拟人朗读）：
{{"summary":"总述一句","slides":[{{"title":"","narration":"","bullet_points":[],"visual_hint":""}}]}}
要求：
- slides 3～5 幕，建议：引入 → 核心概念 → 例子/依据 → 小结
- 每幕 narration 40～90 字，口语化，可直接给虚拟人朗读
- bullet_points 2～4 条短要点；visual_hint 描述画面
- 禁止娱乐化、禁止无关故事
知识点：{name}
侧重：{topic or "通识讲解"}
简介：{_brief_text(planet_desc, 160) or "无"}
校本摘录：
{cite_block}
参考上下文：{rag_ctx or "无"}
"""
        raw = await llm_chat(
            [
                {"role": "system", "content": "只输出 JSON，不要 Markdown。"},
                {"role": "user", "content": llm_prompt},
            ],
            temperature=0.45,
            response_json=True,
            timeout=75.0,
            user_id=user_id,
            endpoint="planet_explain",
        )
        parsed = extract_json(raw or "")
        if isinstance(parsed, dict):
            normalized = _normalize_mistake_slides(parsed.get("slides"))
            if len(normalized) >= 3:
                slides = normalized
                used_llm = True
            if str(parsed.get("summary") or "").strip():
                summary = str(parsed.get("summary")).strip()[:120]

    script_parts = [str(s.get("narration") or "").strip() for s in slides if s.get("narration")]
    spoken = " ".join(script_parts).strip() or script
    return {
        "slides": slides,
        "summary": summary,
        "script": spoken,
        "citations": citations,
        "topic": topic,
        "provider": "planet_gsap",
        "used_llm": used_llm,
    }


async def _start_planet_gsap(
    user: User,
    *,
    planet_slug: str,
    galaxy_slug: str = "",
    planet_name: str = "",
    planet_desc: str = "",
    prompt: str = "",
    force: bool = False,
    word_count: int = 120,
    mode: str = "planet",
) -> dict[str, Any]:
    """行星通识：RAG/DeepSeek 分镜+讲稿，禁止 videoGenerate。"""
    slug = (planet_slug or "").strip()
    if not slug:
        raise ValueError("planet_slug 必填")
    if not force:
        cached = _PLANET_EXPLAIN_CACHE.get(slug)
        if cached and cached.get("slides"):
            out = dict(cached)
            out["cached"] = True
            out["message"] = "已加载该行星的分镜讲稿缓存"
            return _public_task(out)

    explained = await analyze_planet_explain(
        planet_name=planet_name or slug,
        planet_desc=planet_desc,
        prompt=prompt,
        galaxy_slug=galaxy_slug,
        user_id=user.id,
        word_count=word_count,
    )
    local_id = f"dh_p_{uuid.uuid4().hex[:14]}"
    row: dict[str, Any] = {
        "task_id": local_id,
        "status": "succeeded",
        "fallback": False,
        "error": "",
        "message": "行星分镜与讲稿已就绪，可由虚拟人逐幕朗读",
        "planet_slug": slug,
        "galaxy_slug": galaxy_slug or "",
        "planet_name": planet_name or slug,
        "prompt": explained.get("topic") or prompt or planet_name,
        "script": explained["script"],
        "summary": explained.get("summary") or "",
        "slides": explained["slides"],
        "citations": explained.get("citations") or [],
        "video_url": None,
        "remote_video_url": None,
        "cover_image": None,
        "audio_url": None,
        "xf_task_id": None,
        "asset": None,
        "user_id": user.id,
        "provider": "planet_gsap",
        "cached": False,
        "mode": mode if mode in ("planet", "tutor_summary") else "planet",
        "mistake_id": "",
        "source_tag": "digital_tutor" if mode != "tutor_summary" else "digital_tutor_summary",
    }
    if not explained.get("used_llm"):
        row["message"] = "DeepSeek 暂不可用，已使用本地分镜兜底；仍可由虚拟人朗读"
    _TASKS[local_id] = row
    _PLANET_EXPLAIN_CACHE[slug] = dict(row)
    return _public_task(row)


async def _start_mistake_gsap(
    user: User,
    *,
    planet_slug: str = "",
    galaxy_slug: str = "",
    planet_name: str = "错题讲解",
    force: bool = False,
    mistake_id: str = "",
    question: str = "",
    student_answer: str = "",
    correct_answer: str = "",
    note: str = "",
    subject: str = "",
) -> dict[str, Any]:
    """错题模式：DeepSeek 分镜+讲稿，禁止 videoGenerate。"""
    mid = (mistake_id or "").strip()
    if mid and not force:
        cached = _MISTAKE_EXPLAIN_CACHE.get(mid)
        if cached and cached.get("slides"):
            out = dict(cached)
            out["cached"] = True
            out["message"] = "已加载该错题的分镜讲稿缓存"
            return _public_task(out)

    explained = await analyze_mistake_explain(
        question=question,
        student_answer=student_answer,
        correct_answer=correct_answer,
        note=note,
        subject=subject,
        user_id=user.id,
    )
    local_id = f"dh_m_{uuid.uuid4().hex[:14]}"
    row: dict[str, Any] = {
        "task_id": local_id,
        "status": "succeeded",
        "fallback": False,
        "error": "",
        "message": "错题分镜与讲稿已就绪，可由虚拟人逐幕朗读",
        "planet_slug": planet_slug or "",
        "galaxy_slug": galaxy_slug or "",
        "planet_name": planet_name,
        "prompt": f"错题讲解:{_brief_text(question, 40)}",
        "script": explained["script"],
        "summary": explained.get("summary") or "",
        "slides": explained["slides"],
        "citations": [],
        "video_url": None,
        "remote_video_url": None,
        "cover_image": None,
        "audio_url": None,
        "xf_task_id": None,
        "asset": None,
        "user_id": user.id,
        "provider": "mistake_gsap",
        "cached": False,
        "mode": "mistake",
        "mistake_id": mid,
        "source_tag": "digital_tutor_mistake",
    }
    if not explained.get("used_llm"):
        row["message"] = "DeepSeek 暂不可用，已使用本地分镜兜底；仍可由虚拟人朗读"
    _TASKS[local_id] = row
    if mid:
        _MISTAKE_EXPLAIN_CACHE[mid] = dict(row)
    return _public_task(row)


def _inflight_busy() -> bool:
    """是否有进行中的讯飞视频任务；超时则自动释放槽位。"""
    global _INFLIGHT_LOCAL_ID
    if not _INFLIGHT_LOCAL_ID:
        return False
    row = _TASKS.get(_INFLIGHT_LOCAL_ID)
    if not row:
        _INFLIGHT_LOCAL_ID = None
        return False
    st = str(row.get("status") or "")
    if st not in ("processing", "queued"):
        _INFLIGHT_LOCAL_ID = None
        return False
    started = float(row.get("started_at") or 0)
    settings = get_settings()
    limit = float(getattr(settings, "xf_dh_timeout", 900) or 900) + 60
    if started and (time.time() - started) > limit:
        logger.warning(
            "digital tutor inflight stale, releasing slot task=%s age=%.0fs",
            _INFLIGHT_LOCAL_ID,
            time.time() - started,
        )
        row["status"] = "fallback"
        row["fallback"] = True
        row["error"] = "任务超时未完成，已释放并发槽位，可重新生成"
        row["message"] = "占用任务已超时释放"
        _INFLIGHT_LOCAL_ID = None
        return False
    return True


async def start_generate(
    session: AsyncSession,
    user: User,
    *,
    planet_slug: str = "",
    prompt: str = "",
    word_count: int | None = None,
    force: bool = False,
    mode: str = "planet",
    mistake_id: str = "",
    question: str = "",
    student_answer: str = "",
    correct_answer: str = "",
    note: str = "",
    subject: str = "",
) -> dict[str, Any]:
    """创建讲解任务。mode=planet/tutor_summary 走分镜+虚拟人；mistake 走错题分镜。"""
    mode = (mode or "planet").strip().lower()
    if mode not in ("planet", "mistake", "tutor_summary"):
        mode = "planet"

    planet_name = "错题讲解"
    planet_desc = ""
    galaxy_slug = ""
    planet_slug_resolved = (planet_slug or "").strip()
    if planet_slug_resolved:
        try:
            planet, galaxy_slug = await _resolve_planet(session, planet_slug_resolved)
            planet_name = planet.name
            planet_desc = planet.description or ""
            planet_slug_resolved = planet.slug
        except ValueError:
            planet_slug_resolved = planet_slug_resolved or ""
            planet_name = subject.strip() or planet_slug_resolved or "错题讲解"
    elif mode != "mistake":
        raise ValueError("planet_slug 必填")

    # 错题：DeepSeek slides + script，不走 videoGenerate / 并发槽
    if mode == "mistake":
        if not (question or "").strip():
            raise ValueError("错题讲解需要 question")
        return await _start_mistake_gsap(
            user,
            planet_slug=planet_slug_resolved,
            galaxy_slug=galaxy_slug,
            planet_name=planet_name if planet_slug_resolved else (subject.strip() or "错题讲解"),
            force=force,
            mistake_id=mistake_id,
            question=question,
            student_answer=student_answer,
            correct_answer=correct_answer,
            note=note,
            subject=subject,
        )

    # 行星通识 / 伴学摘要：同步分镜，主路径不再走讯飞异步成片
    if not planet_slug_resolved:
        raise ValueError("planet_slug 必填")
    settings = get_settings()
    wc = word_count if word_count is not None else int(getattr(settings, "xf_dh_word_count", 80) or 80)
    wc = max(50, min(120, int(wc)))
    if not planet_name or planet_name == "错题讲解":
        planet, galaxy_slug = await _resolve_planet(session, planet_slug_resolved)
        planet_name = planet.name
        planet_desc = planet.description or ""
        planet_slug_resolved = planet.slug
    return await _start_planet_gsap(
        user,
        planet_slug=planet_slug_resolved,
        galaxy_slug=galaxy_slug,
        planet_name=planet_name,
        planet_desc=planet_desc,
        prompt=prompt,
        force=force,
        word_count=wc,
        mode=mode,
    )


async def _start_generate_video_legacy(
    session: AsyncSession,
    user: User,
    *,
    planet_slug_resolved: str,
    galaxy_slug: str,
    planet_name: str,
    prompt: str = "",
    word_count: int | None = None,
    force: bool = False,
    mode: str = "planet",
    mistake_id: str = "",
) -> dict[str, Any]:
    """遗留：讯飞 videoGenerate 异步成片（主路径已改为 planet_gsap，保留供兼容）。"""
    global _INFLIGHT_LOCAL_ID

    if not force and planet_slug_resolved:
        saved = await find_saved_for_planet(session, planet_slug=planet_slug_resolved)
        if saved and saved.get("video_url"):
            return saved

    settings = get_settings()
    wc = word_count if word_count is not None else int(getattr(settings, "xf_dh_word_count", 80) or 80)
    wc = max(50, min(120, int(wc)))

    if not planet_slug_resolved:
        raise ValueError("planet_slug 必填")
    planet, galaxy_slug = await _resolve_planet(session, planet_slug_resolved)
    planet_name = planet.name
    bundle = build_script_bundle(
        planet_name=planet.name,
        planet_desc=planet.description or "",
        prompt=prompt,
        galaxy_slug=galaxy_slug,
        word_count=wc,
    )
    xf_prompt = bundle["xf_prompt"]
    spoken = bundle["script"]
    citations = bundle["citations"]
    topic = bundle["topic"]
    source_tag = "digital_tutor" if mode == "planet" else "digital_tutor_summary"

    local_id = f"dh_{uuid.uuid4().hex[:16]}"
    row: dict[str, Any] = {
        "task_id": local_id,
        "status": "queued",
        "fallback": False,
        "error": "",
        "message": "任务已创建",
        "planet_slug": planet_slug_resolved,
        "galaxy_slug": galaxy_slug,
        "planet_name": planet_name,
        "prompt": topic,
        "script": spoken,
        "slides": [],
        "summary": "",
        "citations": citations,
        "video_url": None,
        "remote_video_url": None,
        "cover_image": None,
        "audio_url": None,
        "xf_task_id": None,
        "asset": None,
        "user_id": user.id,
        "provider": "xf_digital_human",
        "xf_prompt": xf_prompt,
        "word_count": wc,
        "cached": False,
        "mode": mode,
        "mistake_id": (mistake_id or "").strip(),
        "source_tag": source_tag,
    }
    _TASKS[local_id] = row

    if not xf_dh.xf_digital_human_available():
        row["status"] = "fallback"
        row["fallback"] = True
        row["error"] = (
            "未配置讯飞数字人密钥：请设置 XF_DH_APP_ID / XF_DH_API_KEY / XF_DH_API_SECRET"
            "（或回退使用 XF_APP_ID / XF_API_KEY / XF_API_SECRET）"
        )
        row["message"] = "数字人视频不可用，已提供文案与引用兜底"
        return _public_task(row)

    async with _INFLIGHT_LOCK:
        if _inflight_busy():
            busy = _TASKS.get(_INFLIGHT_LOCAL_ID or "")
            if busy:
                # 并发=1：不新建任务，把进行中的任务交给前端继续轮询
                out = _public_task(busy)
                out["message"] = (
                    f"讯飞并发限制为 1，已接入进行中的任务 "
                    f"{busy.get('task_id') or _INFLIGHT_LOCAL_ID}，请等待云端渲染完成"
                )
                out["reused_inflight"] = True
                # 丢掉本次预创建的空任务，避免污染
                _TASKS.pop(local_id, None)
                return out
            row["status"] = "fallback"
            row["fallback"] = True
            row["error"] = "讯飞数字人视频并发限制为 1，当前槽位异常占用，请稍后重试"
            row["message"] = "并发槽位已占用，已回退到文案讲解"
            return _public_task(row)
        try:
            xf_tid = await xf_dh.create_task(xf_prompt, word_count=wc)
        except Exception as exc:  # noqa: BLE001
            logger.exception("digital tutor create_task failed")
            row["status"] = "fallback"
            row["fallback"] = True
            row["error"] = str(exc)
            row["message"] = "创建数字人任务失败，已回退到文案讲解"
            return _public_task(row)
        _INFLIGHT_LOCAL_ID = local_id
        row["xf_task_id"] = xf_tid
        row["xf_task_status"] = "1"
        row["status"] = "processing"
        row["started_at"] = time.time()
        row["message"] = _xf_status_message("1")

    asyncio.create_task(_run_poll_and_finalize(local_id, user_id=user.id))
    return _public_task(row)



async def _run_poll_and_finalize(local_id: str, *, user_id: str) -> None:
    global _INFLIGHT_LOCAL_ID
    row = _TASKS.get(local_id)
    if not row:
        return
    xf_tid = row.get("xf_task_id")
    if not xf_tid:
        return
    try:

        async def _on_poll(status: Any, payload: dict[str, Any]) -> None:
            r = _TASKS.get(local_id)
            if not r:
                return
            r["status"] = "processing"
            r["xf_task_status"] = str(status or "")
            r["message"] = _xf_status_message(status)
            pl = payload.get("payload")
            if isinstance(pl, dict) and pl.get("text"):
                r["script"] = str(pl["text"])

        result = await xf_dh.poll_until_done(str(xf_tid), on_poll=_on_poll)
        payload = result.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        remote = xf_dh.extract_video_url(payload)
        if payload.get("text"):
            row["script"] = str(payload["text"])
        row["cover_image"] = payload.get("image") or payload.get("image_url")
        row["audio_url"] = payload.get("audio") or payload.get("audio_url")
        row["remote_video_url"] = remote

        if not remote:
            row["status"] = "fallback"
            row["fallback"] = True
            row["error"] = "任务完成但未返回视频地址"
            row["message"] = "未拿到视频，已保留播报文案"
            return

        local_url = await xf_dh.download_video(remote, planet_slug=row.get("planet_slug") or "dh")
        row["video_url"] = local_url
        row["status"] = "succeeded"
        row["message"] = "数字人视频已就绪并保存，下次将直接播放"
        row["fallback"] = False
        row["error"] = ""

        try:
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                user = (
                    await session.execute(select(User).where(User.id == user_id))
                ).scalar_one_or_none()
                if user is not None:
                    planet_name = str(row.get("planet_name") or row.get("planet_slug") or "错题讲解")
                    source_tag = str(row.get("source_tag") or "digital_tutor")
                    meta = {
                        "mode": row.get("mode") or "planet",
                        "source": source_tag,
                        "provider": row.get("provider") or "xf_digital_human",
                        "xf_task_id": row.get("xf_task_id"),
                        "script": row.get("script") or "",
                        "citations": row.get("citations") or [],
                        "prompt": row.get("prompt") or "",
                        "cover_image": row.get("cover_image"),
                        "audio_url": row.get("audio_url"),
                        "remote_video_url": row.get("remote_video_url"),
                        "mistake_id": row.get("mistake_id") or "",
                        "title": planet_name,
                    }
                    existing = (
                        await session.execute(
                            select(StarAsset)
                            .where(StarAsset.asset_type == "video_local")
                            .order_by(StarAsset.created_at.desc())
                            .limit(40)
                        )
                    ).scalars().all()
                    updated = None
                    mid = str(row.get("mistake_id") or "")
                    for cand in existing:
                        cmeta = cand.meta_json if isinstance(cand.meta_json, dict) else {}
                        if mid and str(cmeta.get("source") or "") == "digital_tutor_mistake" and str(cmeta.get("mistake_id") or "") == mid:
                            match = True
                        elif not mid and str(cmeta.get("source") or "") == source_tag and cand.planet_slug == (row.get("planet_slug") or ""):
                            match = True
                        else:
                            match = False
                        if not match:
                            continue
                        cand.file_url = local_url
                        cand.title = f"数字人讲解 · {planet_name}"
                        cand.description = (row.get("script") or "")[:500]
                        cand.meta_json = {**cmeta, **meta}
                        cand.status = "ready"
                        if row.get("planet_slug"):
                            cand.planet_slug = row.get("planet_slug") or cand.planet_slug
                        session.add(cand)
                        await session.commit()
                        await session.refresh(cand)
                        updated = cand
                        break
                    if updated is not None:
                        asset = starlib_svc._row_out(updated)
                    else:
                        asset = await starlib_svc.create_local_video_asset(
                            session,
                            user,
                            title=f"数字人讲解 · {planet_name}",
                            file_url=local_url,
                            galaxy_slug=row.get("galaxy_slug") or "",
                            planet_slug=row.get("planet_slug") or "",
                            description=(row.get("script") or "")[:500],
                            meta_json=meta,
                        )
                    row["asset"] = asset
                    row["cached"] = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("digital tutor save star asset failed: %s", exc)

    except Exception as exc:  # noqa: BLE001
        logger.exception("digital tutor poll failed task=%s", local_id)
        row["status"] = "fallback"
        row["fallback"] = True
        row["error"] = str(exc)
        row["message"] = "数字人生成失败，已回退到文案讲解"
    finally:
        if _INFLIGHT_LOCAL_ID == local_id:
            _INFLIGHT_LOCAL_ID = None


async def query_local_task(task_id: str) -> dict[str, Any]:
    row = _TASKS.get(task_id)
    if row is None:
        raise KeyError(task_id)
    return _public_task(row)

