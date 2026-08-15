import json
import logging
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    SHANGHAI = ZoneInfo("Asia/Shanghai")
except Exception:
    # Windows 未装 tzdata 时回退到固定 UTC+8
    SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def _today_start_shanghai() -> datetime:
    now = datetime.now(SHANGHAI)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Galaxy, Planet
from app.models.mastery import PlanetMastery
from app.models.user import User
from app.models.zone_extras import (
    AchievementMilestone,
    DailyTaskRecord,
    FocusSession,
    GameChallengeRecord,
    MistakeRecord,
    RedeemRecord,
    SignInRecord,
    WishLike,
    WishPost,
)

logger = logging.getLogger(__name__)

SHOP_ITEMS = [
    {"id": "title-stargazer", "name": "星轨领航员", "description": "专属称号", "cost": 30, "kind": "title"},
    {"id": "title-focus", "name": "专注守望者", "description": "专注达成称号", "cost": 50, "kind": "title"},
    {"id": "pet-theveller", "name": "TheVeller 桌宠", "description": "解锁吐司鹅桌宠", "cost": 60, "kind": "pet", "pet_slug": "theveller"},
    {"id": "pet-angry-cat", "name": "Angry Cat 桌宠", "description": "解锁生气猫桌宠", "cost": 60, "kind": "pet", "pet_slug": "angry-cat"},
    {"id": "pet-bitboy", "name": "BitBoy 桌宠", "description": "解锁掌机像素桌宠", "cost": 80, "kind": "pet", "pet_slug": "bitboy"},
    {"id": "pet-mochi-8", "name": "Bunny 桌宠", "description": "解锁复古兔子桌宠", "cost": 80, "kind": "pet", "pet_slug": "mochi-8"},
    {"id": "pet-dordor", "name": "DorDor 桌宠", "description": "解锁古代牧羊犬桌宠", "cost": 80, "kind": "pet", "pet_slug": "dordor"},
    {"id": "pet-zodiac-pig", "name": "Zodiac Pig 桌宠", "description": "解锁生肖猪桌宠", "cost": 100, "kind": "pet", "pet_slug": "zodiac-pig"},
    {"id": "pet-loki", "name": "饭团桌宠", "description": "解锁布偶猫饭团", "cost": 100, "kind": "pet", "pet_slug": "loki"},
    {"id": "pet-wangcai", "name": "Wangcai 桌宠", "description": "解锁旺财桌宠", "cost": 100, "kind": "pet", "pet_slug": "wangcai"},
    {"id": "pet-xiwei", "name": "Xiwei 桌宠", "description": "解锁希微桌宠", "cost": 120, "kind": "pet", "pet_slug": "xiwei"},
    {"id": "pet-ru-ma", "name": "儒马桌宠", "description": "解锁儒马书生桌宠", "cost": 120, "kind": "pet", "pet_slug": "ru-ma"},
    {"id": "audio-rain", "name": "雨声白噪音", "description": "自习室专注音轨", "cost": 20, "kind": "audio"},
    {"id": "audio-nebula", "name": "星云脉冲", "description": "低沉宇宙音景", "cost": 25, "kind": "audio"},
    {"id": "theme-aurora", "name": "极光自习室", "description": "自习区极光粒子主题", "cost": 40, "kind": "theme"},
    {"id": "theme-violet", "name": "紫星云自习室", "description": "自习区深紫星云主题", "cost": 45, "kind": "theme"},
]


async def create_focus_session(session: AsyncSession, user: User, minutes: int, source: str, room_id: str = "") -> FocusSession:
    row = FocusSession(user_id=user.id, minutes=minutes, source=source, room_id=room_id or "")
    session.add(row)
    user.points = int(user.points or 0) + max(1, minutes // 5)
    await session.commit()
    await session.refresh(row)
    return row


async def focus_summary(session: AsyncSession, user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    today = (
        await session.execute(
            select(func.coalesce(func.sum(FocusSession.minutes), 0)).where(
                FocusSession.user_id == user_id, FocusSession.created_at >= today_start
            )
        )
    ).scalar_one()
    week = (
        await session.execute(
            select(func.coalesce(func.sum(FocusSession.minutes), 0)).where(
                FocusSession.user_id == user_id, FocusSession.created_at >= week_start
            )
        )
    ).scalar_one()
    count = (
        await session.execute(select(func.count()).select_from(FocusSession).where(FocusSession.user_id == user_id))
    ).scalar_one()
    return {"today_minutes": int(today or 0), "week_minutes": int(week or 0), "sessions": int(count or 0)}


def _slot_for_hour(hour: int) -> str:
    if hour < 12:
        return "morning"
    if hour < 18:
        return "afternoon"
    return "evening"


async def focus_heatmap(session: AsyncSession, user_id: str, week_offset: int = 0) -> dict:
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday()) + timedelta(weeks=week_offset)
    week_end = week_start + timedelta(days=7)

    rows = (
        await session.execute(
            select(FocusSession).where(
                FocusSession.user_id == user_id,
                FocusSession.created_at >= week_start,
                FocusSession.created_at < week_end,
            )
        )
    ).scalars().all()

    cells: dict[tuple[int, str], int] = {}
    total = 0
    for row in rows:
        created = row.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        day = (created.date() - week_start.date()).days
        if day < 0 or day > 6:
            continue
        slot = _slot_for_hour(created.hour)
        key = (day, slot)
        cells[key] = cells.get(key, 0) + int(row.minutes or 0)
        total += int(row.minutes or 0)

    out_cells = [{"day": d, "slot": s, "minutes": m} for (d, s), m in sorted(cells.items())]
    return {
        "week_start": week_start.date().isoformat(),
        "week_end": (week_end - timedelta(days=1)).date().isoformat(),
        "total_minutes": total,
        "cells": out_cells,
    }


async def focus_leaderboard(session: AsyncSession, limit: int = 10, room_id: str = "") -> list[dict]:
    today_start = _today_start_shanghai().astimezone(timezone.utc)
    stmt = (
        select(FocusSession.user_id, func.sum(FocusSession.minutes).label("mins"))
        .where(FocusSession.created_at >= today_start)
        .group_by(FocusSession.user_id)
        .order_by(func.sum(FocusSession.minutes).desc())
        .limit(limit)
    )
    if room_id:
        stmt = (
            select(FocusSession.user_id, func.sum(FocusSession.minutes).label("mins"))
            .where(FocusSession.created_at >= today_start, FocusSession.room_id == room_id)
            .group_by(FocusSession.user_id)
            .order_by(func.sum(FocusSession.minutes).desc())
            .limit(limit)
        )
    rows = (await session.execute(stmt)).all()
    out = []
    for user_id, mins in rows:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        out.append(
            {
                "user_id": user_id,
                "display_name": (user.display_name if user else user_id[:8]),
                "minutes": int(mins or 0),
            }
        )
    return out


async def _planet_by_slug(session: AsyncSession, slug: str) -> tuple[Planet | None, Galaxy | None]:
    planet = (await session.execute(select(Planet).where(Planet.slug == slug))).scalar_one_or_none()
    if planet is None:
        return None, None
    galaxy = (await session.execute(select(Galaxy).where(Galaxy.id == planet.galaxy_id))).scalar_one_or_none()
    return planet, galaxy


async def explain_knowledge_node(session: AsyncSession, user_id: str, slug: str) -> dict:
    planet, galaxy = await _planet_by_slug(session, slug)
    if planet is None:
        return {"slug": slug, "name": slug, "summary": "未找到该知识点。", "tips": []}
    mastery = (
        await session.execute(
            select(PlanetMastery).where(PlanetMastery.user_id == user_id, PlanetMastery.planet_id == planet.id)
        )
    ).scalar_one_or_none()
    base = f"知识点「{planet.name}」属于{galaxy.name if galaxy else '未知星系'}。"
    summary = base + " 建议先掌握前置概念，再通过练习点亮该行星。"
    tips = ["回顾前置知识点", "完成一次小测巩固", "向教练提问不懂的细节"]
    from app.services.llm import llm_available, llm_chat

    if llm_available():
        try:
            ai = await llm_chat(
                [
                    {"role": "system", "content": "你是 SparkOrbit 学习助手。用 JSON 输出：{\"summary\":\"80字内核心摘要\",\"tips\":[\"建议1\",\"建议2\",\"建议3\"]}"},
                    {"role": "user", "content": f"请讲解知识点：{planet.name}，简介：{planet.description or planet.name}，掌握度：{float(mastery.score or 0) if mastery else 0}"},
                ],
                temperature=0.5,
            )
            if ai:
                data = json.loads(ai.strip().strip('`').removeprefix('json'))
                summary = str(data.get("summary", summary))
                tips = [str(x) for x in data.get("tips", tips)][:4]
        except Exception:
            logger.exception("knowledge explain llm failed")
    return {"slug": slug, "name": planet.name, "galaxy": galaxy.name if galaxy else "", "summary": summary, "tips": tips}


async def ask_knowledge(session: AsyncSession, user_id: str, slug: str, question: str) -> dict:
    planet, galaxy = await _planet_by_slug(session, slug)
    if planet is None:
        return {"answer": "未找到该知识点，请换一个节点提问。"}
    from app.services.llm import llm_available, llm_chat

    if not llm_available():
        return {"answer": f"关于「{planet.name}」：{question}。建议结合教材与课堂笔记继续深入。"}
    try:
        answer = await llm_chat(
            [
                {"role": "system", "content": "你是 SparkOrbit 星链答疑助手，针对单个知识点用简洁中文回答学生问题，不超过200字。"},
                {"role": "user", "content": f"知识点：{planet.name}（{galaxy.name if galaxy else ''}）\n问题：{question}"},
            ],
            temperature=0.6,
        )
        return {"answer": (answer or "").strip() or "暂时无法生成回答，请稍后再试。"}
    except Exception:
        logger.exception("knowledge ask llm failed")
        return {"answer": "智能答疑暂时不可用，请稍后再试。"}


async def generate_ai_quiz(session: AsyncSession, user_id: str, slug: str) -> dict:
    planet, galaxy = await _planet_by_slug(session, slug)
    if planet is None:
        return {"slug": slug, "questions": []}
    questions = [
        {"q": f"请简述 {planet.name} 的核心概念。", "hint": "结合课堂笔记"},
        {"q": f"举一个与 {planet.name} 相关的实际应用场景。", "hint": "联系生活或项目"},
    ]
    from app.services.llm import llm_available, llm_chat

    if llm_available():
        try:
            ai = await llm_chat(
                [
                    {"role": "system", "content": "生成 JSON：{\"questions\":[{\"q\":\"题目\",\"hint\":\"提示\"}]}，共3道中文简答题。"},
                    {"role": "user", "content": f"围绕知识点 {planet.name} 出测验题"},
                ],
                temperature=0.7,
            )
            if ai:
                data = json.loads(ai.strip().strip('`').removeprefix('json'))
                questions = data.get("questions", questions)[:3]
        except Exception:
            logger.exception("ai quiz llm failed")
    return {"slug": slug, "name": planet.name, "questions": questions}


async def submit_ai_quiz(
    session: AsyncSession,
    user_id: str,
    *,
    slug: str,
    question_index: int,
    answer: str,
    self_ok: bool | None = None,
) -> dict:
    planet, _galaxy = await _planet_by_slug(session, slug)
    name = planet.name if planet else slug
    quiz = await generate_ai_quiz(session, user_id, slug)
    questions = quiz.get("questions") or []
    q = ""
    if 0 <= question_index < len(questions):
        q = str(questions[question_index].get("q") or "")
    text = (answer or "").strip()
    correct = bool(self_ok) if self_ok is not None else len(text) >= 12
    feedback = (
        "回答较充实，已记入学习事件，建议继续行星挑战巩固。"
        if correct
        else "回答偏短或自评未掌握，已记入薄弱证据；可打开提示后重答，或去行星挑战。"
    )
    from app.services.profile_refresh import record_learning_event

    await record_learning_event(
        session,
        user_id,
        "ai_quiz_submit",
        f"智能测验{'通过' if correct else '待补'}：{name}",
        {
            "planet_slug": slug,
            "question_index": question_index,
            "question": q,
            "answer": text[:500],
            "correct": correct,
        },
    )
    return {
        "ok": True,
        "correct": correct,
        "feedback": feedback,
        "message": "已写入随学随新事件，可继续四闸或路径打卡",
    }


async def focus_yearly_calendar(session: AsyncSession, user_id: str) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=364)
    rows = (
        await session.execute(
            select(FocusSession).where(FocusSession.user_id == user_id, FocusSession.created_at >= start)
        )
    ).scalars().all()
    day_map: dict[str, int] = {}
    day_sessions: dict[str, int] = {}
    for row in rows:
        created = row.created_at
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        key = created.date().isoformat()
        day_map[key] = day_map.get(key, 0) + int(row.minutes or 0)
        day_sessions[key] = day_sessions.get(key, 0) + 1
    cells = [
        {"date": k, "minutes": v, "sessions": day_sessions.get(k, 0)}
        for k, v in sorted(day_map.items())
    ]
    return {"cells": cells, "total_minutes": sum(day_map.values())}


PET_PLAY_MIN_SCORE = 15


async def record_leisure_session(session: AsyncSession, user: User, game: str, score: int, won: bool) -> dict:
    awarded = 0
    affinity_delta = 0
    message = "继续加油"

    if game == "pet-play":
        if score < PET_PLAY_MIN_SCORE:
            message = f"连击 {score} 下，达到 {PET_PLAY_MIN_SCORE} 下才有积分"
        else:
            awarded = min(3, 1 + (score - PET_PLAY_MIN_SCORE) // 10)
            affinity_delta = min(3, 1 + (score - PET_PLAY_MIN_SCORE) // 12)
            user.points = int(user.points or 0) + awarded
            user.pet_affinity = int(user.pet_affinity or 0) + affinity_delta
            session.add(user)
            await session.commit()
            message = f"连击 {score} 下，获得 {awarded} 积分"
    elif won or score >= 5:
        awarded = min(5, max(1, score // 10))
        user.points = int(user.points or 0) + awarded
        session.add(user)
        await session.commit()
        message = f"获得 {awarded} 积分"

    return {
        "points_awarded": awarded,
        "total_points": int(user.points or 0),
        "message": message,
        "pet_affinity_delta": affinity_delta,
    }


async def list_shop_owned(session: AsyncSession, user_id: str) -> list[dict]:
    rows = (
        await session.execute(
            select(RedeemRecord).where(RedeemRecord.user_id == user_id).order_by(RedeemRecord.created_at.desc())
        )
    ).scalars().all()
    catalog = {x["id"]: x for x in SHOP_ITEMS}
    return [
        {
            "item_id": row.item_id,
            "item_name": row.item_name,
            "cost": row.cost,
            "kind": catalog.get(row.item_id, {}).get("kind", ""),
            "pet_slug": catalog.get(row.item_id, {}).get("pet_slug", ""),
            "redeemed_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]


async def ocr_mistake_from_image(image_bytes: bytes, content_type: str) -> dict:
    from app.services.ark_vision import ark_vision_available, ark_vision_chat
    from app.services.llm import extract_json

    if not ark_vision_available():
        return {
            "question": "请手动输入题目（未配置火山方舟视觉接入点 ARK_VISION_MODEL）",
            "student_answer": "",
            "correct_answer": "",
            "subject": "",
            "note": "",
        }
    import base64

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = content_type or "image/jpeg"
    prompt = (
        "请识别这张错题图片中的题目内容，并尽量提取学生答案与正确答案。"
        '严格返回 JSON：{"question":"","student_answer":"","correct_answer":"","subject":"","note":""}'
    )
    raw = await ark_vision_chat(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        temperature=0.3,
        timeout=90.0,
        endpoint="mistake_ocr_vision",
    )
    if not raw:
        return {
            "question": "请手动输入题目（识图失败，请重试）",
            "student_answer": "",
            "correct_answer": "",
            "subject": "",
            "note": "",
        }
    try:
        parsed = extract_json(raw)
        if isinstance(parsed, dict):
            return {
                "question": str(parsed.get("question") or ""),
                "student_answer": str(parsed.get("student_answer") or ""),
                "correct_answer": str(parsed.get("correct_answer") or ""),
                "subject": str(parsed.get("subject") or ""),
                "note": str(parsed.get("note") or ""),
            }
    except Exception:
        logger.exception("ocr mistake parse failed")
    return {"question": raw[:500], "student_answer": "", "correct_answer": "", "subject": "", "note": ""}


async def ocr_mistakes_batch_from_image(image_bytes: bytes, content_type: str) -> list[dict]:
    """批量识别：一张图可能含多道错题，返回结构化列表（不入库，供前端预览确认）。"""
    from app.services.ark_vision import ark_vision_available, ark_vision_chat
    from app.services.llm import extract_json_list

    if not ark_vision_available():
        raise RuntimeError("视觉识别不可用（未配置 ARK_VISION_MODEL），请手动录入")

    import base64

    b64 = base64.b64encode(image_bytes).decode("ascii")
    mime = content_type or "image/jpeg"
    prompt = (
        "这张图片可能包含一道或多道题目（试卷 / 作业 / 错题本照片）。"
        "请识别出全部题目，逐题提取：题目内容、学生作答（有批改痕迹时）、正确答案（能推断时）、学科。"
        '严格返回 JSON：{"questions":[{"question":"","student_answer":"","correct_answer":"","subject":"","note":""}]}'
    )
    raw = await ark_vision_chat(
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        temperature=0.2,
        timeout=120.0,
        endpoint="mistake_ocr_batch",
    )
    if not raw:
        raise RuntimeError("识图失败，请重试")
    items = extract_json_list(raw) or []
    out: list[dict] = []
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        out.append(
            {
                "question": question[:2000],
                "student_answer": str(item.get("student_answer") or "")[:1000],
                "correct_answer": str(item.get("correct_answer") or "")[:1000],
                "subject": str(item.get("subject") or "")[:64],
                "note": str(item.get("note") or "")[:500],
            }
        )
    if not out:
        raise RuntimeError("未能从图片中识别出题目，请换一张更清晰的照片")
    return out


async def list_mistakes(session: AsyncSession, user_id: str) -> list[MistakeRecord]:
    return list(
        (
            await session.execute(
                select(MistakeRecord).where(MistakeRecord.user_id == user_id).order_by(MistakeRecord.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def add_mistake(session: AsyncSession, user: User, payload: dict) -> MistakeRecord:
    row = MistakeRecord(user_id=user.id, **payload)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def delete_mistake(session: AsyncSession, user_id: str, mistake_id: str) -> bool:
    row = (
        await session.execute(
            select(MistakeRecord).where(MistakeRecord.id == mistake_id, MistakeRecord.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def list_wishes(session: AsyncSession, user_id: str) -> list[dict]:
    rows = (await session.execute(select(WishPost).order_by(WishPost.created_at.desc()).limit(50))).scalars().all()
    likes = (
        await session.execute(select(WishLike.wish_id).where(WishLike.user_id == user_id))
    ).scalars().all()
    liked = set(likes)
    return [
        {
            "id": w.id,
            "user_id": w.user_id,
            "display_name": w.display_name,
            "content": w.content,
            "likes": w.likes,
            "liked_by_me": w.id in liked,
            "created_at": w.created_at.isoformat() if w.created_at else "",
        }
        for w in rows
    ]


async def create_wish(session: AsyncSession, user: User, content: str) -> dict:
    row = WishPost(user_id=user.id, display_name=user.display_name or user.username, content=content.strip())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "id": row.id,
        "user_id": row.user_id,
        "display_name": row.display_name,
        "content": row.content,
        "likes": 0,
        "liked_by_me": False,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


async def like_wish(session: AsyncSession, user_id: str, wish_id: str) -> WishPost | None:
    wish = (await session.execute(select(WishPost).where(WishPost.id == wish_id))).scalar_one_or_none()
    if wish is None:
        return None
    existing = (
        await session.execute(select(WishLike).where(WishLike.wish_id == wish_id, WishLike.user_id == user_id))
    ).scalar_one_or_none()
    if existing is None:
        session.add(WishLike(wish_id=wish_id, user_id=user_id))
        wish.likes = int(wish.likes or 0) + 1
        await session.commit()
        await session.refresh(wish)
    return wish


async def list_shop_items() -> list[dict]:
    return list(SHOP_ITEMS)


async def redeem_item(session: AsyncSession, user: User, item_id: str) -> dict:
    item = next((x for x in SHOP_ITEMS if x["id"] == item_id), None)
    if item is None:
        raise ValueError("商品不存在")
    if int(user.points or 0) < item["cost"]:
        raise ValueError("积分不足")
    existing = (
        await session.execute(
            select(RedeemRecord).where(RedeemRecord.user_id == user.id, RedeemRecord.item_id == item_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("已拥有该商品")
    user.points = int(user.points or 0) - item["cost"]
    pet_slug = ""
    if item.get("kind") == "pet":
        pet_slug = str(item.get("pet_slug") or "").strip()
        if pet_slug:
            user.pet_slug = pet_slug
    session.add(RedeemRecord(user_id=user.id, item_id=item_id, item_name=item["name"], cost=item["cost"]))
    await session.commit()
    return {"ok": True, "points": user.points, "item": item, "pet_slug": pet_slug or None}


async def list_achievements(session: AsyncSession, user: User) -> list[dict]:
    from app.models.mastery import PlanetMastery

    summary = await focus_summary(session, user.id)
    lit_count = (
        await session.execute(
            select(func.count()).select_from(PlanetMastery).where(
                PlanetMastery.user_id == user.id, PlanetMastery.status == "lit"
            )
        )
    ).scalar_one()
    defs = [
        {"id": "first-light", "name": "初见星光", "description": "点亮 1 颗行星", "icon": "✨", "progress": int(lit_count or 0), "target": 1},
        {"id": "orbit-5", "name": "星轨五连", "description": "点亮 5 颗行星", "icon": "🪐", "progress": int(lit_count or 0), "target": 5},
        {"id": "focus-60", "name": "一小时专注", "description": "累计专注 60 分钟", "icon": "⏱️", "progress": summary["week_minutes"], "target": 60},
        {"id": "streak-3", "name": "三日星火", "description": "连续学习 3 天", "icon": "🔥", "progress": int(user.streak_days or 0), "target": 3},
        {"id": "points-100", "name": "百星积分", "description": "积分达到 100", "icon": "⭐", "progress": int(user.points or 0), "target": 100},
    ]
    for d in defs:
        d["unlocked"] = d["progress"] >= d["target"]
        if d["unlocked"]:
            existing = (
                await session.execute(
                    select(AchievementMilestone).where(
                        AchievementMilestone.user_id == user.id,
                        AchievementMilestone.achievement_id == d["id"],
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(
                    AchievementMilestone(
                        user_id=user.id,
                        achievement_id=d["id"],
                        achievement_name=d["name"],
                    )
                )
    await session.commit()
    return defs


async def list_milestones(session: AsyncSession, user_id: str) -> list[dict]:
    rows = (
        await session.execute(
            select(AchievementMilestone)
            .where(AchievementMilestone.user_id == user_id)
            .order_by(AchievementMilestone.unlocked_at.desc())
            .limit(30)
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "achievement_id": r.achievement_id,
            "achievement_name": r.achievement_name,
            "unlocked_at": r.unlocked_at.isoformat() if r.unlocked_at else "",
        }
        for r in rows
    ]


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def ensure_daily_tasks(session: AsyncSession, user: User) -> list[dict]:
    today = _today_str()
    _ = today
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (
        await session.execute(
            select(DailyTaskRecord).where(
                DailyTaskRecord.user_id == user.id,
                DailyTaskRecord.created_at >= day_start,
            )
        )
    ).scalars().all()

    # 始终尝试补齐复习任务（教师扫描或学生自打开均可）
    try:
        from app.services.memory_decay import ensure_review_daily_tasks

        await ensure_review_daily_tasks(session, user, max_tasks=3, commit=True)
        rows = (
            await session.execute(
                select(DailyTaskRecord).where(
                    DailyTaskRecord.user_id == user.id,
                    DailyTaskRecord.created_at >= day_start,
                )
            )
        ).scalars().all()
    except Exception:  # noqa: BLE001
        pass

    if rows:
        return [
            {"id": r.id, "title": r.title, "task_type": r.task_type, "done": r.done, "points": r.points}
            for r in rows
        ]

    weak_planets = (
        await session.execute(
            select(Planet.name)
            .join(PlanetMastery, PlanetMastery.planet_id == Planet.id)
            .where(PlanetMastery.user_id == user.id, PlanetMastery.status != "lit")
            .limit(1)
        )
    ).scalar_one_or_none()
    planet_hint = weak_planets or "下一颗行星"

    templates = [
        {"title": f"点亮或复习「{planet_hint}」", "task_type": "learn", "points": 8},
        {"title": "完成 25 分钟番茄专注", "task_type": "focus", "points": 10},
        {"title": "在班级群分享一条学习打卡", "task_type": "social", "points": 5},
    ]
    out = []
    for tpl in templates:
        row = DailyTaskRecord(user_id=user.id, **tpl)
        session.add(row)
        await session.flush()
        out.append({"id": row.id, "title": row.title, "task_type": row.task_type, "done": row.done, "points": row.points})
    await session.commit()
    return out


async def toggle_daily_task(session: AsyncSession, user: User, task_id: str) -> dict | None:
    row = (
        await session.execute(
            select(DailyTaskRecord).where(DailyTaskRecord.id == task_id, DailyTaskRecord.user_id == user.id)
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    row.done = not row.done
    if row.done:
        row.completed_at = datetime.now(timezone.utc)
        user.points = int(user.points or 0) + int(row.points or 0)
        session.add(user)
    else:
        row.completed_at = None
    session.add(row)
    await session.commit()
    return {"id": row.id, "title": row.title, "task_type": row.task_type, "done": row.done, "points": row.points}


async def sign_in_today(session: AsyncSession, user: User) -> dict:
    today = _today_str()
    existing = (
        await session.execute(
            select(SignInRecord).where(SignInRecord.user_id == user.id, SignInRecord.day == today)
        )
    ).scalar_one_or_none()
    if existing is not None:
        calendar = await _sign_in_calendar(session, user.id)
        return {"signed_today": True, "streak": existing.streak, "points_awarded": 0, "calendar": calendar}

    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    prev = (
        await session.execute(
            select(SignInRecord).where(SignInRecord.user_id == user.id, SignInRecord.day == yesterday)
        )
    ).scalar_one_or_none()
    streak = (prev.streak + 1) if prev else 1
    points = min(20, 3 + streak)
    user.points = int(user.points or 0) + points
    session.add(SignInRecord(user_id=user.id, day=today, streak=streak, points_awarded=points))
    session.add(user)
    await session.commit()
    calendar = await _sign_in_calendar(session, user.id)
    return {"signed_today": True, "streak": streak, "points_awarded": points, "calendar": calendar}


async def _sign_in_calendar(session: AsyncSession, user_id: str, days: int = 7) -> list[dict]:
    start = datetime.now(timezone.utc) - timedelta(days=days - 1)
    rows = (
        await session.execute(
            select(SignInRecord).where(SignInRecord.user_id == user_id, SignInRecord.created_at >= start)
        )
    ).scalars().all()
    signed_days = {r.day for r in rows}
    out = []
    for i in range(days):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        out.append({"day": d, "signed": d in signed_days})
    return out


async def fetch_sign_in_status(session: AsyncSession, user_id: str) -> dict:
    today = _today_str()
    existing = (
        await session.execute(
            select(SignInRecord).where(SignInRecord.user_id == user_id, SignInRecord.day == today)
        )
    ).scalar_one_or_none()
    calendar = await _sign_in_calendar(session, user_id)
    streak = existing.streak if existing else 0
    if not existing:
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        prev = (
            await session.execute(
                select(SignInRecord).where(SignInRecord.user_id == user_id, SignInRecord.day == yesterday)
            )
        ).scalar_one_or_none()
        streak = prev.streak if prev else 0
    return {"signed_today": existing is not None, "streak": streak, "points_awarded": 0, "calendar": calendar}


async def study_streak_calendar(session: AsyncSession, user_id: str) -> dict:
    start = datetime.now(timezone.utc) - timedelta(days=13)
    rows = (
        await session.execute(
            select(FocusSession).where(
                FocusSession.user_id == user_id,
                FocusSession.source.in_(["pomodoro", "study_room"]),
                FocusSession.created_at >= start,
            )
        )
    ).scalars().all()
    days_with_study: set[str] = set()
    for row in rows:
        if row.created_at:
            days_with_study.add(row.created_at.strftime("%Y-%m-%d"))
    calendar = []
    for i in range(14):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        calendar.append({"day": d, "studied": d in days_with_study})
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    return {"streak_days": int(user.streak_days or 0) if user else 0, "calendar": calendar}


async def knowledge_graph(session: AsyncSession, user_id: str) -> dict:
    galaxies = (await session.execute(select(Galaxy).order_by(Galaxy.sort_order))).scalars().all()
    nodes: list[dict] = []
    edges: list[dict] = []
    prev_slug: str | None = None
    for galaxy in galaxies:
        planets = (
            await session.execute(select(Planet).where(Planet.galaxy_id == galaxy.id).order_by(Planet.orbit_index))
        ).scalars().all()
        for planet in planets:
            mastery = (
                await session.execute(
                    select(PlanetMastery).where(PlanetMastery.user_id == user_id, PlanetMastery.planet_id == planet.id)
                )
            ).scalar_one_or_none()
            status = mastery.status if mastery else "dim"
            score = float(mastery.score or 0) if mastery else 0.0
            nodes.append(
                {
                    "id": planet.slug,
                    "name": planet.name,
                    "slug": planet.slug,
                    "galaxy": galaxy.name,
                    "status": status,
                    "mastery": score,
                }
            )
            if prev_slug:
                edges.append({"source": prev_slug, "target": planet.slug})
            prev_slug = planet.slug
    return {"nodes": nodes, "edges": edges}


def _format_recent_activity(mastery_rows: list[PlanetMastery], answered_at: datetime | None) -> str:
    """拼一条近期动态文案（点亮/答题），与进度榜展示一致。"""
    lit_recent = None
    for m in mastery_rows:
        if m.status == "lit" and m.lit_at:
            if lit_recent is None or m.lit_at > lit_recent:
                lit_recent = m.lit_at
    candidates = [t for t in (lit_recent, answered_at) if t is not None]
    if not candidates:
        return "暂无近期学习记录"
    latest = max(candidates)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    delta = now - latest.astimezone(timezone.utc)
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        when = "刚刚"
    elif minutes < 60:
        when = f"{minutes} 分钟前"
    elif minutes < 1440:
        when = f"{minutes // 60} 小时前"
    else:
        when = f"{minutes // 1440} 天前"
    if lit_recent and (answered_at is None or lit_recent >= answered_at):
        return f"{when}点亮了行星"
    return f"{when}完成了挑战答题"


async def progress_board(session: AsyncSession, user: User) -> dict:
    """学习榜：班级同学或全站学生的点亮/掌握概览（口径与 avatar mastery_rate 一致）。"""
    from app.models.mastery import ChallengeQuestion
    from app.models.school_class import SchoolClass

    total_planets = len((await session.execute(select(Planet))).scalars().all())
    scope = "site"
    scope_label = "全站学习榜"
    students: list[User] = []

    if user.class_id:
        cls = (
            await session.execute(select(SchoolClass).where(SchoolClass.id == user.class_id))
        ).scalar_one_or_none()
        students = (
            await session.execute(
                select(User).where(User.class_id == user.class_id, User.role == "student")
            )
        ).scalars().all()
        if students:
            scope = "class"
            scope_label = f"{cls.name} · 学习榜" if cls else "本班学习榜"

    if not students:
        students = (
            await session.execute(
                select(User).where(User.role == "student").order_by(User.display_name).limit(80)
            )
        ).scalars().all()
        scope = "site"
        scope_label = "全站学习榜"

    items: list[dict] = []
    for s in students:
        mastery_rows = (
            await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == s.id))
        ).scalars().all()
        lit = sum(1 for m in mastery_rows if m.status == "lit")
        rate = round((lit / total_planets) * 100) if total_planets else 0
        last_q = (
            await session.execute(
                select(ChallengeQuestion)
                .where(ChallengeQuestion.user_id == s.id, ChallengeQuestion.answered.is_(True))
                .order_by(ChallengeQuestion.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        answered_at = last_q.created_at if last_q else None
        items.append(
            {
                "user_id": s.id,
                "display_name": s.display_name or s.username,
                "lit_count": lit,
                "total_planets": total_planets,
                "mastery_rate": rate,
                "recent_activity": _format_recent_activity(list(mastery_rows), answered_at),
                "is_me": s.id == user.id,
            }
        )

    items.sort(key=lambda x: (-x["mastery_rate"], -x["lit_count"], x["display_name"]))
    return {
        "scope": scope,
        "scope_label": scope_label,
        "total_planets": total_planets,
        "students": items,
    }


async def buddy_matches(session: AsyncSession, user: User, limit: int = 5) -> list[dict]:
    if not user.class_id:
        return []
    classmates = (
        await session.execute(
            select(User).where(User.class_id == user.class_id, User.id != user.id, User.role == "student")
        )
    ).scalars().all()
    my_focus = (
        await session.execute(
            select(func.coalesce(func.sum(FocusSession.minutes), 0)).where(FocusSession.user_id == user.id)
        )
    ).scalar_one()
    out = []
    for mate in classmates[:limit]:
        mate_focus = (
            await session.execute(
                select(func.coalesce(func.sum(FocusSession.minutes), 0)).where(FocusSession.user_id == mate.id)
            )
        ).scalar_one()
        diff = abs(int(my_focus or 0) - int(mate_focus or 0))
        complement = max(10, 100 - diff)
        reason = "专注节奏互补，适合组队自习" if diff > 30 else "进度相近，适合一起刷题"
        out.append(
            {
                "user_id": mate.id,
                "display_name": mate.display_name,
                "reason": reason,
                "complement_score": complement,
            }
        )
    out.sort(key=lambda x: x["complement_score"], reverse=True)
    return out[:limit]


async def create_game_challenge(session: AsyncSession, user: User, target_user_id: str, game: str, score: int) -> dict:
    target = (await session.execute(select(User).where(User.id == target_user_id))).scalar_one_or_none()
    if target is None:
        raise ValueError("目标用户不存在")
    row = GameChallengeRecord(
        challenger_id=user.id,
        target_id=target_user_id,
        game=game,
        challenger_score=score,
        status="pending",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return {
        "id": row.id,
        "challenger_name": user.display_name,
        "target_name": target.display_name,
        "game": row.game,
        "challenger_score": row.challenger_score,
        "target_score": row.target_score,
        "status": row.status,
    }


async def respond_game_challenge(session: AsyncSession, user: User, challenge_id: str, score: int) -> dict:
    row = (
        await session.execute(select(GameChallengeRecord).where(GameChallengeRecord.id == challenge_id))
    ).scalar_one_or_none()
    if row is None or row.target_id != user.id:
        raise ValueError("挑战不存在")
    row.target_score = score
    row.status = "done"
    challenger = (await session.execute(select(User).where(User.id == row.challenger_id))).scalar_one_or_none()
    winner = row.challenger_id if row.challenger_score >= row.target_score else row.target_id
    winner_user = (await session.execute(select(User).where(User.id == winner))).scalar_one_or_none()
    if winner_user:
        winner_user.points = int(winner_user.points or 0) + 3
        session.add(winner_user)
    session.add(row)
    await session.commit()
    return {
        "id": row.id,
        "challenger_name": challenger.display_name if challenger else "",
        "target_name": user.display_name,
        "game": row.game,
        "challenger_score": row.challenger_score,
        "target_score": row.target_score,
        "status": row.status,
    }


async def list_pending_challenges(session: AsyncSession, user_id: str) -> list[dict]:
    rows = (
        await session.execute(
            select(GameChallengeRecord)
            .where(GameChallengeRecord.target_id == user_id, GameChallengeRecord.status == "pending")
            .order_by(GameChallengeRecord.created_at.desc())
        )
    ).scalars().all()
    out = []
    for row in rows:
        challenger = (await session.execute(select(User).where(User.id == row.challenger_id))).scalar_one_or_none()
        out.append(
            {
                "id": row.id,
                "challenger_name": challenger.display_name if challenger else "",
                "target_name": "",
                "game": row.game,
                "challenger_score": row.challenger_score,
                "target_score": row.target_score,
                "status": row.status,
            }
        )
    return out
