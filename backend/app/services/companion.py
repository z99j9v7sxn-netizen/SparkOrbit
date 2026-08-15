"""Companion Agent：知心伴读 / 苏格拉底式学习答疑 + 碎片闯关。"""
from collections.abc import AsyncGenerator
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.user import User
from app.schemas.galaxy import CompanionChatRequest, CompanionChatResponse, TutorSourceRef
from app.services.fragments import grant_fragment_on_chat
from app.services.spark import spark_chat, spark_chat_stream

COMPANION_SYSTEM = """你是 SparkOrbit 星轨学图中的 Companion Agent（知心学习伙伴）。
你的任务是情绪疏导与陪伴：当学生表达疲惫、焦虑、挫败时，用温暖、鼓励、真诚的语气回应，
给予具体可执行的小建议（如番茄钟、拆分目标、先点亮一颗简单行星）。
语气亲切自然，像同龄伙伴，不要说教，不要长篇大论，控制在 120 字以内。"""

TUTOR_SOCRATIC_SYSTEM = """你是 SparkOrbit 星轨学图中的 Tutor Agent，采用苏格拉底式引导辅导。
铁律：
1. 先问后讲：首轮与前几轮必须以启发性问题引导，禁止直接给出最终答案、完整题解或可直接抄写的结论。
2. 可给线索：允许给类比、反例方向、检查清单式提示，但必须配套至少一个反问。
3. 边界：只围绕给定知识点 ID 与描述作答，禁止编造超纲内容；若依据不足，明确说「需要先确认你对 X 的理解」。
4. 篇幅：控制在 180 字以内；语气耐心、像教练而非百科。
5. 当学生已展示正确推理时，可简短确认并给下一步巩固建议，仍避免长篇灌输。"""

TUTOR_DIRECT_SYSTEM = """你是 SparkOrbit 星轨学图中的 Tutor Agent（耐心的学习答疑老师）。
学生会就某个知识点提问，请用清晰、循序渐进的方式讲解核心概念，
必要时举一个简单例子帮助理解，避免堆砌术语。控制在 200 字以内。
只围绕给定知识点边界作答，禁止编造超纲内容。"""

FEYNMAN_SYSTEM = """你是 SparkOrbit 的 Feynman Tutor（费曼学习法教练）。
学生会用自己的话讲解某个知识点。你的任务：
1. 先简短复述学生理解中正确的部分；
2. 指出漏洞、含糊表述或常见误区（至少 1 点）；
3. 用一个追问迫使学生补全缺口；
4. 若讲解已基本正确，给予简短确认并提出一个巩固小任务。
禁止直接替学生重讲完整定义。点评文字控制在 180 字以内。

必须只返回 JSON（不要 markdown 代码块）：
{"reply":"给学生的点评…","score":0.0到1.0,"completeness":0.0到1.0,"accuracy":0.0到1.0,"examples":0.0到1.0,"pass":true或false}
评分约定：基本正确且可过讲闸 score≥0.75；有明显漏洞 0.45~0.7；严重错误或空话 <0.45。pass 与 score≥0.75 一致。"""

FALLBACK_COMPANION = "我在这儿陪着你～先深呼吸一下。学不进去很正常，不如先点亮一颗最简单的行星找回手感，我们一步步来，你可以的！"
FALLBACK_TUTOR_SOCRATIC = (
    "先别急着要标准答案。你现在对这个知识点的「定义」能用自己的话讲一句吗？"
    "如果卡壳，可以说说你卡在哪一步——我们一步步拆。（配置 DeepSeek 后引导会更贴合。）"
)
FALLBACK_TUTOR_DIRECT = (
    "这个知识点的关键在于理解它的核心定义与典型场景。"
    "建议先看一个最小例子，再回到定义对照，最后做一道题巩固。（配置 DeepSeek 后我能给你更详细的讲解。）"
)
FALLBACK_FEYNMAN = (
    "我听到了你的讲解。先肯定：你抓住了部分直觉。"
    "不过有一处还比较含糊——你能指出这个概念的「适用边界」或一个反例吗？"
    "用自己的话再补一句，我们继续。（配置 DeepSeek 后点评会更细。）"
)


async def _load_planet(session: Optional[AsyncSession], planet_slug: str) -> Optional[Planet]:
    if not session or not planet_slug:
        return None
    return (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()


def _build_sources(planet: Optional[Planet], rag_snippets: Optional[List[dict]] = None) -> List[TutorSourceRef]:
    sources: List[TutorSourceRef] = []
    if planet:
        snippet = (planet.description or planet.name or "")[:200]
        sources.append(
            TutorSourceRef(
                galaxy=str(getattr(planet, "galaxy_id", "") or ""),
                source=f"planet:{planet.slug}",
                snippet=snippet or planet.name,
                knowledge_point_id=planet.slug,
            )
        )
    for item in rag_snippets or []:
        sources.append(
            TutorSourceRef(
                galaxy=str(item.get("galaxy", "")),
                source=str(item.get("source", "rag")),
                snippet=str(item.get("snippet", ""))[:240],
                knowledge_point_id=str(item.get("knowledge_point_id", "")),
            )
        )
    return sources


def _tutor_system(socratic: bool) -> str:
    return TUTOR_SOCRATIC_SYSTEM if socratic else TUTOR_DIRECT_SYSTEM


def _tutor_fallback(socratic: bool) -> str:
    return FALLBACK_TUTOR_SOCRATIC if socratic else FALLBACK_TUTOR_DIRECT


async def _resolve_bounded_context(
    session: Optional[AsyncSession],
    req: CompanionChatRequest,
    *,
    system: str,
    student_label: str,
) -> tuple[str, str, List[TutorSourceRef]]:
    planet = await _load_planet(session, req.planet_slug or "")
    rag_snippets: List[dict] = []
    rag_text = ""
    try:
        from app.services.rag import build_rag_context, query_sources

        query = planet.name if planet else (req.planet_slug or req.message[:80])
        rag_text = build_rag_context(query) or ""
        rag_snippets = query_sources(query, n=2) if query else []
    except Exception:  # noqa: BLE001
        rag_text = ""
        rag_snippets = []

    boundary_parts = [
        f"知识点 ID：{planet.slug if planet else (req.planet_slug or '未知')}",
        f"知识点名称：{planet.name if planet else (req.planet_slug or '未知')}",
    ]
    if planet and planet.description:
        boundary_parts.append(f"知识点描述：{planet.description[:400]}")
    if rag_text:
        boundary_parts.append(f"校本依据摘录：\n{rag_text[:800]}")

    user_content = "\n".join(boundary_parts) + f"\n\n{student_label}：\n{req.message}"
    sources = _build_sources(planet, rag_snippets)
    return system, user_content, sources


async def _resolve_tutor_context(
    session: Optional[AsyncSession],
    req: CompanionChatRequest,
) -> tuple[str, str, List[TutorSourceRef]]:
    """返回 (system, user_content, sources)。"""
    mode = req.mode if req.mode in ("companion", "tutor", "feynman") else "companion"
    if mode == "companion":
        return COMPANION_SYSTEM, req.message, []
    if mode == "feynman":
        return await _resolve_bounded_context(
            session, req, system=FEYNMAN_SYSTEM, student_label="学生用自己的话讲解"
        )

    socratic = True if req.socratic is None else bool(req.socratic)
    return await _resolve_bounded_context(
        session, req, system=_tutor_system(socratic), student_label="学生提问"
    )


def _parse_feynman_payload(raw: str) -> tuple[str, Optional[float], Optional[dict]]:
    """解析费曼 JSON；失败则整段当 reply。"""
    from app.services.spark import extract_json

    data = extract_json(raw) if raw else None
    if not isinstance(data, dict):
        return (raw or "").strip(), None, None
    reply = str(data.get("reply") or data.get("feedback") or "").strip() or (raw or "").strip()
    try:
        score = float(data.get("score"))
        score = max(0.0, min(1.0, score))
    except (TypeError, ValueError):
        score = None
    rubric = {
        "completeness": data.get("completeness"),
        "accuracy": data.get("accuracy"),
        "examples": data.get("examples"),
        "pass": data.get("pass"),
    }
    return reply, score, rubric


async def companion_chat(
    req: CompanionChatRequest,
    session: AsyncSession | None = None,
    user_id: str | None = None,
) -> CompanionChatResponse:
    mode = req.mode if req.mode in ("companion", "tutor", "feynman") else "companion"
    socratic = True if req.socratic is None else bool(req.socratic)

    system, user_content, sources = await _resolve_tutor_context(session, req)

    content = await spark_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        temperature=0.7 if mode in ("tutor", "feynman") else 0.8,
    )
    if not content:
        if mode == "companion":
            content = FALLBACK_COMPANION
        elif mode == "feynman":
            content = FALLBACK_FEYNMAN
        else:
            content = _tutor_fallback(socratic)

    explain_score: Optional[float] = None
    explain_rubric: Optional[dict] = None
    if mode == "feynman":
        content, explain_score, explain_rubric = _parse_feynman_payload(content)
        if explain_score is None and content == FALLBACK_FEYNMAN:
            explain_score = 0.55
            explain_rubric = {"pass": False, "note": "fallback"}

    fragment_progress = None
    explain_gate: Optional[dict] = None
    if session and user_id and req.planet_slug:
        fragment_progress = await grant_fragment_on_chat(session, user_id, req.planet_slug, req.message)
        if mode == "feynman":
            try:
                from sqlalchemy import select

                from app.models.galaxy import Planet
                from app.services import mastery_gates as gates
                from app.services.gate_policy import get_thresholds_for_user
                from app.services.learning_path import sync_path_after_mastery_change
                from app.services.profile_refresh import record_learning_event, refresh_profile_from_events
                from app.models.user import User as UserModel

                planet = (
                    await session.execute(select(Planet).where(Planet.slug == req.planet_slug))
                ).scalar_one_or_none()
                score_val = float(explain_score) if explain_score is not None else 0.0
                passed = bool((explain_rubric or {}).get("pass")) or score_val >= 0.75
                user_row = await session.get(UserModel, user_id)
                if planet is not None:
                    mastery = await gates.ensure_mastery(session, user_id, planet.id)
                    thresholds = await get_thresholds_for_user(session, user_row, "") if user_row else {}
                    snap = gates.pass_explain_gate(mastery, score=score_val, policy=thresholds)
                    lit = False
                    if passed:
                        lit = gates.try_light_planet(mastery)
                        if lit and user_row is not None:
                            user_row.points = int(getattr(user_row, "points", 0) or 0) + 10
                            session.add(user_row)
                    explain_gate = {**snap, "lit": lit, "score": score_val}
                    await session.commit()

                await record_learning_event(
                    session,
                    user_id=user_id,
                    event_type="feynman_explain",
                    summary=f"费曼讲解 {req.planet_slug}：{(req.message or '')[:80]}",
                    payload={
                        "planet_slug": req.planet_slug,
                        "reply_preview": content[:120],
                        "explain_score": explain_score,
                        "pass": passed,
                        "gate": explain_gate,
                    },
                )
                await refresh_profile_from_events(session, user_id)
                if user_row is not None and (passed or score_val >= 0.6):
                    try:
                        await sync_path_after_mastery_change(session, user_row)
                    except Exception:  # noqa: BLE001
                        pass
            except Exception:  # noqa: BLE001
                try:
                    await session.commit()
                except Exception:  # noqa: BLE001
                    pass

    return CompanionChatResponse(
        reply=content.strip(),
        mode=mode,
        fragment_progress=fragment_progress,
        socratic=socratic if mode == "tutor" else False,
        sources=sources or None,
        explain_score=explain_score,
        explain_rubric=explain_rubric,
        explain_gate=explain_gate,
    )


async def _companion_messages(
    req: CompanionChatRequest,
    session: Optional[AsyncSession] = None,
) -> tuple[str, str, List[Any]]:
    return await _resolve_tutor_context(session, req)


async def companion_chat_stream(
    req: CompanionChatRequest,
    session: Optional[AsyncSession] = None,
    user_id: str = "",
) -> AsyncGenerator[str, None]:
    system, user_content, _sources = await _companion_messages(req, session=session)
    mode = req.mode if req.mode in ("companion", "tutor", "feynman") else "companion"
    socratic = True if req.socratic is None else bool(req.socratic)
    got = False
    async for token in spark_chat_stream(
        [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
        temperature=0.7 if mode in ("tutor", "feynman") else 0.8,
        user_id=user_id,
        endpoint="companion_chat",
    ):
        got = True
        yield token
    if not got:
        if mode == "companion":
            yield FALLBACK_COMPANION
        elif mode == "feynman":
            yield FALLBACK_FEYNMAN
        else:
            yield _tutor_fallback(socratic)


async def selection_ask(
    *,
    quote: str | None = None,
    planet_slug: str | None = None,
    question: str | None = None,
    asset_id: str | None = None,
    page_no: int | None = None,
    image_base64: str | None = None,
    image_mime: str | None = None,
    mode: str | None = "tutor",
    socratic: bool | None = True,
    session: AsyncSession | None = None,
    user: User | None = None,
) -> dict[str, Any]:
    """划词/画笔提问：以 quote 或区域截图为上下文调用 Tutor/RAG，并记 selection_ask 学闸证据。"""
    ask_mode = mode if mode in ("tutor", "feynman") else "tutor"
    ask_socratic = True if socratic is None else bool(socratic)
    system = FEYNMAN_SYSTEM if ask_mode == "feynman" else _tutor_system(ask_socratic)

    quote_text = (quote or "").strip()
    img_b64 = (image_base64 or "").strip()
    # 允许 data URL 前缀
    if img_b64.startswith("data:") and "," in img_b64:
        header, img_b64 = img_b64.split(",", 1)
        if not image_mime and ";" in header:
            image_mime = header.split(";")[0].removeprefix("data:") or image_mime

    planet = await _load_planet(session, planet_slug or "")
    rag_snippets: List[dict] = []
    rag_text = ""
    query = (question or quote_text or "教材截图提问")[:200]
    try:
        from app.services.rag import build_rag_context, query_sources

        rag_text = build_rag_context(query) or ""
        rag_snippets = query_sources(query, n=3) if query else []
    except Exception:  # noqa: BLE001
        rag_text = ""
        rag_snippets = []

    context_parts: list[str] = []
    if quote_text:
        context_parts.append(f"学生划词摘录：\n{quote_text[:2000]}")
    if img_b64:
        context_parts.append("学生用画笔框选了教材截图（见附图），请识别图中文字与公式并结合其意图作答。")
    if page_no is not None:
        context_parts.append(f"页码：{page_no}")
    if asset_id:
        context_parts.append(f"资产 ID：{asset_id}")
    if planet:
        context_parts.append(f"知识点：{planet.name}（{planet.slug}）")
        if planet.description:
            context_parts.append(f"知识点描述：{planet.description[:400]}")
    if rag_text:
        context_parts.append(f"校本依据摘录：\n{rag_text[:800]}")
    if question:
        if ask_mode == "feynman":
            context_parts.append(f"学生用自己的话讲解：{question[:500]}")
        else:
            context_parts.append(f"学生追问：{question[:500]}")
    elif ask_mode == "feynman":
        context_parts.append("请引导学生用自己的话讲解框选/划词内容，再挑漏洞追问；按费曼 JSON 格式回复。")
    elif ask_socratic:
        context_parts.append("请围绕划词/截图内容用苏格拉底式引导回答，先问后讲，禁止直接甩完整答案。")
    else:
        context_parts.append("请围绕划词/截图内容直接讲解要点，可适当举例。")

    user_text = "\n\n".join(context_parts)
    content: str | None = None

    if img_b64:
        from app.services.ark_vision import ark_vision_available, ark_vision_chat

        mime = (image_mime or "image/jpeg").strip() or "image/jpeg"
        if ark_vision_available():
            # 豆包多模态：区域图 + 文本上下文（火山方舟接入点）
            content = await ark_vision_chat(
                [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                            },
                        ],
                    },
                ],
                temperature=0.6,
                timeout=90.0,
                user_id=getattr(user, "id", "") or "",
                endpoint="selection_ask_vision",
            )
        if not content:
            # 无视觉能力时退回文本路径（若有划词）或提示
            if quote_text:
                content = await spark_chat(
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user_text},
                    ],
                    temperature=0.6,
                )
            else:
                content = (
                    "当前识图服务未就绪（请配置火山方舟 ARK_VISION_MODEL 接入点）。"
                    "请在追问框补充框选区域的关键文字，或改用可复制文字的 PDF 划词提问。"
                )
    else:
        content = await spark_chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            temperature=0.6,
        )

    explain_score: Optional[float] = None
    explain_rubric: Optional[dict] = None
    if ask_mode == "feynman":
        if not content:
            content = FALLBACK_FEYNMAN
        content, explain_score, explain_rubric = _parse_feynman_payload(content)
        if explain_score is None and content == FALLBACK_FEYNMAN:
            explain_score = 0.55
            explain_rubric = {"pass": False, "note": "fallback"}
    elif not content:
        content = _tutor_fallback(ask_socratic)

    sources = _build_sources(planet, rag_snippets)
    gates_out: dict[str, Any] | None = None
    if session and user and planet:
        try:
            from app.services.gate_policy import get_thresholds_for_user
            from app.services import mastery_gates as gates

            mastery = await gates.ensure_mastery(session, user.id, planet.id)
            thresholds = await get_thresholds_for_user(session, user, "")
            detail_bits: list[str] = []
            if quote_text:
                detail_bits.append(quote_text[:120])
            if img_b64:
                detail_bits.append("brush")
            if page_no is not None:
                detail_bits.append(f"p{page_no}")
            if asset_id:
                detail_bits.append(f"asset:{asset_id[:8]}")
            gates_out = gates.record_learn_evidence(
                mastery,
                kind="selection_ask",
                ref_id=asset_id or "",
                detail=" · ".join(detail_bits) or "selection_ask",
                policy=thresholds,
            )
            if ask_mode == "feynman":
                try:
                    from app.services.profile_refresh import record_learning_event, refresh_profile_from_events

                    await record_learning_event(
                        session,
                        user_id=user.id,
                        event_type="feynman_explain",
                        summary=f"费曼讲解 {planet.slug}：{(question or quote_text or '')[:80]}",
                        payload={
                            "planet_slug": planet.slug,
                            "reply_preview": content[:120],
                            "explain_score": explain_score,
                            "source": "selection_ask",
                        },
                    )
                    await refresh_profile_from_events(session, user.id)
                except Exception:  # noqa: BLE001
                    pass
            await session.commit()
        except Exception:  # noqa: BLE001
            try:
                await session.rollback()
            except Exception:  # noqa: BLE001
                pass

    return {
        "answer": content.strip(),
        "citations": [s.model_dump() for s in sources] if sources else None,
        "gates": gates_out,
        "explain_score": explain_score,
        "explain_rubric": explain_rubric,
    }
