"""个性化学习路径规划与资源推荐。"""
from __future__ import annotations

import json
import uuid
from typing import Any, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.learning import LearningPath
from app.models.mastery import PlanetMastery
from app.models.student_profile import DIMENSION_LABELS
from app.models.user import User
from app.schemas.resource_gen import LearningPathOut, LearningPathStepOut, RecommendationItem
from app.services.llm import extract_json, llm_available, llm_chat
from app.services.profiles import get_latest_profile
from app.services.resource_agents import list_user_resources


def _weak_dims_from_profile(profile) -> list[str]:
    if not profile:
        return []
    weak: list[str] = []
    for dim in (
        "prior_knowledge",
        "mistake_tendency",
        "cognitive_style",
        "time_flexibility",
        "modality_preference",
        "motivation_level",
    ):
        data = getattr(profile, dim, None) or {}
        if isinstance(data, dict) and int(data.get("score") or 100) < 60:
            weak.append(str(DIMENSION_LABELS.get(dim, dim)))
    return weak


def _modality_preferred_kinds(profile) -> list[str]:
    """Map modality_preference text to resource kind priority."""
    if not profile:
        return []
    data = getattr(profile, "modality_preference", None) or {}
    text = str(data.get("value") or "") if isinstance(data, dict) else ""
    if any(k in text for k in ("视听", "视频", "动画")):
        return ["media", "deck", "doc", "quiz", "code", "mindmap", "reading"]
    if any(k in text for k in ("实操", "代码", "动手", "编程")):
        return ["code", "quiz", "doc", "media", "mindmap", "deck", "reading"]
    if any(k in text for k in ("文本", "阅读", "文档", "看书")):
        return ["doc", "reading", "mindmap", "quiz", "deck", "media", "code"]
    return []


def _kind_reason_for_weak(weak_dims: list[str], kind: str) -> str:
    labels = "、".join(weak_dims) if weak_dims else ""
    kind_hint = {
        "quiz": "易错/掌握偏弱，建议先练题巩固",
        "code": "偏实操或动机需拉动，建议动手案例",
        "media": "视听偏好或认知负荷，建议动画讲解",
        "doc": "文本偏好，建议系统讲解文档",
        "reading": "拓展阅读补盲区",
        "mindmap": "梳理知识结构",
        "deck": "课件串讲提效",
        "planet": "优先点亮薄弱行星",
    }
    base = kind_hint.get(kind, "基于学习画像推荐")
    if labels:
        return f"{base}（薄弱维：{labels}）"
    return base


def _normalize_mounted(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    out: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        mid = str(item.get("id") or "").strip()
        if not kind or not mid:
            continue
        entry = {
            "kind": kind,
            "id": mid,
            "title": str(item.get("title") or mid),
        }
        reason = str(item.get("reason") or "").strip()
        if reason:
            entry["reason"] = reason
        out.append(entry)
    return out


def _normalize_weak_dims(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value if x]
    return []


async def _mastery_map(session: AsyncSession, user_id: str) -> dict[str, dict]:
    rows = (await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == user_id))).scalars().all()
    planets = (await session.execute(select(Planet))).scalars().all()
    pmap = {p.id: p for p in planets}
    out: dict[str, dict] = {}
    for m in rows:
        p = pmap.get(m.planet_id)
        if not p:
            continue
        out[p.slug] = {"status": m.status, "score": m.score, "name": p.name}
    return out


async def generate_learning_path(
    session: AsyncSession,
    user: User,
    goal: str = "",
    evaluation_hints: Optional[List[str]] = None,
) -> LearningPathOut:
    profile = await get_latest_profile(session, user_id=user.id)
    mastery = await _mastery_map(session, user.id)
    planets = (await session.execute(select(Planet).order_by(Planet.orbit_index))).scalars().all()

    weak = [p for p in planets if mastery.get(p.slug, {}).get("status") != "lit"]
    if not weak:
        weak = planets[:8]

    steps_data: list[dict] = []
    if llm_available():
        weak_planets = [
            {
                "slug": p.slug,
                "name": p.name,
                "score": mastery.get(p.slug, {}).get("score", 0),
            }
            for p in weak[:12]
        ]
        prompt = f"""你是 PathPlanner Agent。根据学生画像与学习数据，生成个性化学习路径 JSON：
{{"title":"路径标题","steps":[{{"planet_slug":"","planet_name":"","action":"","resource_kinds":["doc","quiz"],"reason":"","estimated_minutes":30}}]}}
学习目标：{goal or '系统推荐'}
画像摘要：{getattr(profile, 'summary', '') if profile else '无'}
未点亮/薄弱行星：{json.dumps(weak_planets, ensure_ascii=False)}
评估建议：{evaluation_hints or []}
生成 5-8 步有序学习步骤。"""
        raw = await llm_chat(
            [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
            temperature=0.5,
            response_json=True,
            user_id=user.id,
            endpoint="learn_path_generate",
        )
        if raw:
            parsed = extract_json(raw)
            if parsed and isinstance(parsed.get("steps"), list):
                steps_data = parsed["steps"]
                title = parsed.get("title") or "个性化学习路径"
            else:
                title = "个性化学习路径"
        else:
            title = "个性化学习路径"
    else:
        title = "个性化学习路径"

    if not steps_data:
        title = goal or "点亮薄弱行星路径"
        for i, p in enumerate(weak[:6]):
            steps_data.append(
                {
                    "planet_slug": p.slug,
                    "planet_name": p.name,
                    "action": "学习讲解并完成测验",
                    "resource_kinds": ["doc", "quiz"],
                    "reason": f"掌握度 {mastery.get(p.slug, {}).get('score', 0)}%，建议优先突破",
                    "estimated_minutes": 25 + i * 5,
                    "completed": False,
                    "mounted": [],
                    "weak_dims": [],
                }
            )

    weak_dims = _weak_dims_from_profile(profile)
    for step in steps_data:
        if not isinstance(step, dict):
            continue
        step.setdefault("mounted", [])
        if weak_dims and not step.get("weak_dims"):
            step["weak_dims"] = list(weak_dims)

    row = LearningPath(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=title,
        steps=steps_data,
        status="active",
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _path_to_out(row)


def _normalize_resource_kinds(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_minutes(value: Any) -> int:
    if isinstance(value, (int, float)):
        return max(1, int(value))
    if isinstance(value, str):
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            return max(1, int(digits))
    return 30


def _path_to_out(row: LearningPath) -> LearningPathOut:
    steps_raw = row.steps or []
    steps: list[LearningPathStepOut] = []
    for raw in steps_raw:
        if not isinstance(raw, dict):
            continue
        steps.append(
            LearningPathStepOut(
                planet_slug=str(raw.get("planet_slug") or ""),
                planet_name=str(raw.get("planet_name") or ""),
                action=str(raw.get("action") or ""),
                resource_kinds=_normalize_resource_kinds(raw.get("resource_kinds")),
                reason=str(raw.get("reason") or ""),
                estimated_minutes=_normalize_minutes(raw.get("estimated_minutes")),
                completed=bool(raw.get("completed")),
                mounted=_normalize_mounted(raw.get("mounted")),
                weak_dims=_normalize_weak_dims(raw.get("weak_dims")),
                day=int(raw.get("day") or 0),
                date=str(raw.get("date") or ""),
            )
        )
    done = sum(1 for s in steps if s.completed)
    progress = (done / len(steps) * 100) if steps else 0.0
    return LearningPathOut(
        id=row.id,
        title=row.title,
        goal=row.title,
        steps=steps,
        status=row.status,
        progress=round(progress, 1),
        created_at=row.created_at.isoformat() if row.created_at else "",
        kind=getattr(row, "kind", "") or "standard",
        meta=getattr(row, "meta_json", None) or {},
    )


async def _active_path_row(session: AsyncSession, user_id: str) -> LearningPath | None:
    return (
        await session.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.status == "active",
                LearningPath.kind != "sprint",
            )
            .order_by(desc(LearningPath.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()


# ---------------- 考试冲刺模式 ----------------


async def generate_sprint_path(
    session: AsyncSession,
    user: User,
    *,
    exam_name: str,
    exam_date: str,
) -> LearningPathOut:
    """按天倒排的考前冲刺计划：结合薄弱行星与错题，输出每日清单。"""
    from datetime import date as date_cls, timedelta

    try:
        target = date_cls.fromisoformat(exam_date)
    except ValueError as exc:
        raise ValueError("exam_date 格式应为 YYYY-MM-DD") from exc
    today = date_cls.today()
    days_left = (target - today).days
    if days_left < 1:
        raise ValueError("考试日期需晚于今天")
    days_plan = min(days_left, 21)

    mastery = await _mastery_map(session, user.id)
    weak_list = [
        {"slug": slug, "name": m.get("name", slug), "score": m.get("score", 0)}
        for slug, m in mastery.items()
        if m.get("status") != "lit"
    ][:12]

    # 错题科目分布，用于安排回炉
    from app.models.zone_extras import MistakeRecord
    from sqlalchemy import func as sa_func

    mistake_rows = (
        await session.execute(
            select(MistakeRecord.subject, sa_func.count(MistakeRecord.id))
            .where(MistakeRecord.user_id == user.id)
            .group_by(MistakeRecord.subject)
        )
    ).all()
    mistake_summary = {(s or "未分类"): int(c) for s, c in mistake_rows}

    steps_data: list[dict] = []
    title = f"{exam_name or '考试'} 冲刺计划"
    if llm_available():
        prompt = f"""你是备考冲刺教练。学生将在 {days_left} 天后参加「{exam_name or '考试'}」，请生成 {days_plan} 天冲刺计划 JSON：
{{"title":"计划标题","steps":[{{"day":1,"planet_slug":"","planet_name":"当天主题","action":"当天具体任务（30-60 分钟可完成）","resource_kinds":["quiz"],"reason":"安排理由","estimated_minutes":40}}]}}
薄弱知识点：{json.dumps(weak_list, ensure_ascii=False)}
错题分布：{json.dumps(mistake_summary, ensure_ascii=False)}
规则：每天 1-2 条任务；前期补薄弱、中期专项刷题与错题回炉、最后 2 天全真模考与查漏；day 从 1 递增到 {days_plan}。"""
        raw = await llm_chat(
            [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
            temperature=0.5,
            response_json=True,
            user_id=user.id,
            endpoint="sprint_path_generate",
        )
        if raw:
            parsed = extract_json(raw)
            if parsed and isinstance(parsed.get("steps"), list):
                steps_data = [s for s in parsed["steps"] if isinstance(s, dict)]
                title = str(parsed.get("title") or title)

    if not steps_data:
        # 降级：规则化排期（薄弱点轮换 + 末段模考）
        for i in range(days_plan):
            if i >= days_plan - 2:
                action, kinds = "全真模考一套并复盘错题", ["quiz"]
                name = "模考冲刺"
            elif weak_list:
                w = weak_list[i % len(weak_list)]
                action, kinds = f"突破「{w['name']}」并完成一组练习", ["doc", "quiz"]
                name = str(w["name"])
            else:
                action, kinds = "专项刷题一组 + 错题回炉", ["quiz"]
                name = "综合训练"
            steps_data.append(
                {
                    "day": i + 1,
                    "planet_slug": "",
                    "planet_name": name,
                    "action": action,
                    "resource_kinds": kinds,
                    "reason": "冲刺降级排期",
                    "estimated_minutes": 40,
                }
            )

    for s in steps_data:
        day = int(s.get("day") or 0)
        day = max(1, min(day or 1, days_plan))
        s["day"] = day
        s["date"] = (today + timedelta(days=day - 1)).isoformat()
        s.setdefault("completed", False)
        s.setdefault("mounted", [])
        s.setdefault("weak_dims", [])

    # 同一时间只保留一个活跃冲刺计划
    old_rows = (
        await session.execute(
            select(LearningPath).where(
                LearningPath.user_id == user.id,
                LearningPath.kind == "sprint",
                LearningPath.status == "active",
            )
        )
    ).scalars().all()
    for old in old_rows:
        old.status = "archived"

    row = LearningPath(
        id=str(uuid.uuid4()),
        user_id=user.id,
        title=title,
        steps=steps_data,
        status="active",
        kind="sprint",
        meta_json={"exam_name": exam_name, "exam_date": exam_date, "days_left": days_left},
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _path_to_out(row)


async def get_sprint_path(session: AsyncSession, user_id: str) -> Optional[LearningPathOut]:
    row = (
        await session.execute(
            select(LearningPath)
            .where(
                LearningPath.user_id == user_id,
                LearningPath.kind == "sprint",
                LearningPath.status == "active",
            )
            .order_by(desc(LearningPath.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    return _path_to_out(row) if row else None


async def complete_sprint_step(
    session: AsyncSession, user_id: str, path_id: str, step_index: int
) -> LearningPathOut:
    row = (
        await session.execute(
            select(LearningPath).where(LearningPath.id == path_id, LearningPath.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise ValueError("冲刺计划不存在")
    steps = list(row.steps or [])
    if step_index < 0 or step_index >= len(steps):
        raise ValueError("步骤索引无效")
    step = dict(steps[step_index]) if isinstance(steps[step_index], dict) else {}
    steps[step_index] = {**step, "completed": True}
    row.steps = steps
    if all(s.get("completed") for s in steps if isinstance(s, dict)):
        row.status = "completed"
    await session.commit()
    await session.refresh(row)
    return _path_to_out(row)


async def get_active_path(session: AsyncSession, user_id: str) -> Optional[LearningPathOut]:
    row = await _active_path_row(session, user_id)
    return _path_to_out(row) if row else None


async def complete_path_step(session: AsyncSession, user_id: str, step_index: int) -> LearningPathOut:
    row = await _active_path_row(session, user_id)
    if row is None:
        raise ValueError("暂无进行中的学习路径")
    steps = list(row.steps or [])
    if step_index < 0 or step_index >= len(steps):
        raise ValueError("步骤索引无效")
    step = dict(steps[step_index]) if isinstance(steps[step_index], dict) else {}
    steps[step_index] = {**step, "completed": True}
    row.steps = steps
    if all(s.get("completed") for s in steps):
        row.status = "completed"
    await session.commit()
    await session.refresh(row)

    try:
        from app.services.profile_refresh import record_learning_event

        planet_name = str(step.get("planet_name") or step.get("planet_slug") or f"步骤{step_index + 1}")
        action = str(step.get("action") or "完成路径步骤")
        await record_learning_event(
            session,
            user_id,
            "path_step_complete",
            f"完成路径步骤：{planet_name} · {action}",
            {
                "step_index": step_index,
                "planet_slug": step.get("planet_slug"),
                "planet_name": planet_name,
                "action": action,
            },
        )
    except Exception:
        pass

    return _path_to_out(row)


async def mount_path_step(
    session: AsyncSession,
    user_id: str,
    step_index: int,
    *,
    kind: str,
    item_id: str,
    title: str = "",
    reason: str = "",
    unmount: bool = False,
) -> LearningPathOut:
    row = await _active_path_row(session, user_id)
    if row is None:
        raise ValueError("暂无进行中的学习路径")
    steps = list(row.steps or [])
    if step_index < 0 or step_index >= len(steps):
        raise ValueError("步骤索引无效")
    step = dict(steps[step_index]) if isinstance(steps[step_index], dict) else {}
    mounted = _normalize_mounted(step.get("mounted"))
    kind = str(kind or "").strip()
    item_id = str(item_id or "").strip()
    if not kind or not item_id:
        raise ValueError("kind 与 id 不能为空")

    if unmount:
        mounted = [m for m in mounted if not (m.get("kind") == kind and m.get("id") == item_id)]
    else:
        entry = {"kind": kind, "id": item_id, "title": title or item_id}
        if reason:
            entry["reason"] = reason
        # 同 kind+id 去重替换
        mounted = [m for m in mounted if not (m.get("kind") == kind and m.get("id") == item_id)]
        mounted.append(entry)
        if not step.get("weak_dims"):
            profile = await get_latest_profile(session, user_id=user_id)
            weak = _weak_dims_from_profile(profile)
            if weak:
                step["weak_dims"] = weak

    step["mounted"] = mounted
    steps[step_index] = step
    row.steps = steps
    await session.commit()
    await session.refresh(row)
    return _path_to_out(row)


async def build_recommendations(session: AsyncSession, user: User) -> List[RecommendationItem]:
    profile = await get_latest_profile(session, user_id=user.id)
    mastery = await _mastery_map(session, user.id)
    resources = await list_user_resources(session, user.id)
    recs: list[RecommendationItem] = []

    weak_dim_keys: list[str] = []
    weak_labels = _weak_dims_from_profile(profile)
    if profile:
        for dim in ("prior_knowledge", "mistake_tendency", "modality_preference", "motivation_level"):
            data = getattr(profile, dim, None) or {}
            if isinstance(data, dict) and int(data.get("score") or 100) < 60:
                weak_dim_keys.append(dim)

    preferred = _modality_preferred_kinds(profile)

    planets = (await session.execute(select(Planet))).scalars().all()
    for p in planets:
        m = mastery.get(p.slug, {})
        if m.get("status") == "lit":
            continue
        reason = _kind_reason_for_weak(weak_labels, "planet")
        reason = f"{reason}；掌握度 {m.get('score', 0)}%"
        recs.append(
            RecommendationItem(
                kind="planet",
                title=f"点亮 {p.name}",
                reason=reason,
                planet_slug=p.slug,
                planet_name=p.name,
            )
        )
        if len(recs) >= 5:
            break

    sorted_resources = list(resources)
    if preferred:
        rank = {k: i for i, k in enumerate(preferred)}
        sorted_resources.sort(key=lambda r: rank.get(str(r.get("kind") or ""), 99))

    for r in sorted_resources[:5]:
        kind = str(r.get("kind") or "doc")
        reason = _kind_reason_for_weak(weak_labels, kind)
        if preferred and kind in preferred[:3]:
            reason += "；匹配你的资源模态偏好"
        motive = getattr(profile, "motivation_level", None) or {} if profile else {}
        if isinstance(motive, dict) and int(motive.get("score") or 100) < 50:
            reason += "；动机偏弱，建议短周期完成"
        recs.append(
            RecommendationItem(
                kind=kind,
                title=r["title"],
                reason=reason,
                resource_id=r["id"],
                planet_slug=r["planet_slug"],
                planet_name=r["planet_name"],
            )
        )
    return recs[:10]


async def sync_remediation_steps_to_path(
    session: AsyncSession,
    user: User,
    *,
    topic: str,
    steps: list[str],
    root_cause: str = "",
    target_dimension: str = "",
) -> LearningPathOut:
    """Merge simulation/improvement remediation steps into the active LearningPath (or create one)."""
    clean_steps = [str(s).strip() for s in steps if str(s).strip()]
    if not clean_steps:
        raise ValueError("补救步骤为空")

    profile = await get_latest_profile(session, user_id=user.id)
    weak = _weak_dims_from_profile(profile)
    if target_dimension and target_dimension in DIMENSION_LABELS:
        label = DIMENSION_LABELS[target_dimension]
        if label not in weak:
            weak = [label, *weak]

    path_steps = []
    for i, text in enumerate(clean_steps):
        path_steps.append(
            {
                "planet_slug": "",
                "planet_name": topic or "补救练习",
                "action": text,
                "resource_kinds": ["quiz", "doc"],
                "reason": root_cause or "镜像预演补救步骤",
                "estimated_minutes": 20,
                "completed": False,
                "weak_dims": weak,
                "mounted": [],
                "from_remediation": True,
                "remediation_index": i,
            }
        )

    row = await _active_path_row(session, user.id)
    if row is None:
        row = LearningPath(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title=f"补救路径 · {topic or '镜像预演'}",
            status="active",
            steps=path_steps,
        )
        session.add(row)
    else:
        existing = list(row.steps or [])
        # append remediation steps, keep existing progress
        existing.extend(path_steps)
        row.steps = existing
        row.status = "active"
        if topic and topic not in (row.title or ""):
            row.title = f"{row.title} · 补救：{topic}" if row.title else f"补救路径 · {topic}"
    await session.commit()
    await session.refresh(row)
    return _path_to_out(row)


async def sync_path_after_mastery_change(
    session: AsyncSession,
    user: User,
    *,
    force: bool = False,
) -> Optional[LearningPathOut]:
    """掌握度/讲闸变化后，按最新薄弱点重排或刷新活动路径。"""
    mastery = await _mastery_map(session, user.id)
    weak_slugs = {slug for slug, m in mastery.items() if m.get("status") != "lit"}
    active = await _active_path_row(session, user.id)
    if active is None:
        return await generate_learning_path(session, user, goal="掌握度变化后的推荐路径")

    steps = list(active.steps or [])
    pending_slugs = {
        str(s.get("planet_slug") or "")
        for s in steps
        if isinstance(s, dict) and not s.get("completed")
    }
    pending_slugs.discard("")
    drift = len(weak_slugs.symmetric_difference(pending_slugs))
    if not force and drift < 2 and pending_slugs:
        return _path_to_out(active)

    hints = [f"薄弱点：{slug}" for slug in list(weak_slugs)[:8]]
    return await generate_learning_path(
        session,
        user,
        goal="根据最新掌握度自动重排",
        evaluation_hints=hints or ["掌握度更新"],
    )
