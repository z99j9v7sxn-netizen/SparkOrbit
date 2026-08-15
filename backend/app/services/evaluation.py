"""学习效果多维评估报告。"""
from __future__ import annotations

from collections import Counter
from typing import Any, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mastery import PlanetMastery
from app.models.user import User
from app.models.zone_extras import FocusSession, MistakeRecord
from app.schemas.resource_gen import EvaluationReportOut
from app.services.llm import extract_json, llm_available, llm_chat
from app.services.learning_path import _mastery_map
from app.services.profiles import get_latest_profile
from app.services.resource_agents import list_user_resources


def _aggregate_learn_evidence(session_rows: list[PlanetMastery]) -> tuple[int, dict[str, Any]]:
    """从 mastery.learn_evidence 聚合热力摘要。"""
    by_kind: Counter[str] = Counter()
    by_day: Counter[str] = Counter()
    selection_ask_count = 0
    for row in session_rows:
        raw = getattr(row, "learn_evidence", None)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind") or "unknown")
            by_kind[kind] += 1
            if kind == "selection_ask":
                selection_ask_count += 1
            at = str(item.get("at") or "")
            day = at[:10] if len(at) >= 10 else "unknown"
            by_day[day] += 1
    summary: dict[str, Any] = {
        "by_kind": dict(by_kind),
        "by_day": dict(sorted(by_day.items())),
        "total_evidence": sum(by_kind.values()),
    }
    return selection_ask_count, summary


async def build_evaluation_report(session: AsyncSession, user: User) -> EvaluationReportOut:
    mastery = await _mastery_map(session, user.id)
    total = len(mastery) or 1
    lit = sum(1 for m in mastery.values() if m.get("status") == "lit")
    mastery_rate = round(lit / total * 100, 1)

    mastery_rows = (
        await session.execute(select(PlanetMastery).where(PlanetMastery.user_id == user.id))
    ).scalars().all()
    selection_ask_count, learn_heatmap_summary = _aggregate_learn_evidence(list(mastery_rows))

    mistakes = (
        await session.execute(select(func.count()).select_from(MistakeRecord).where(MistakeRecord.user_id == user.id))
    ).scalar() or 0

    focus_minutes = (
        await session.execute(select(func.coalesce(func.sum(FocusSession.minutes), 0)).where(FocusSession.user_id == user.id))
    ).scalar() or 0

    resources = await list_user_resources(session, user.id)
    profile = await get_latest_profile(session, user_id=user.id)

    base = EvaluationReportOut(
        summary=f"已点亮 {lit}/{total} 颗行星，掌握率约 {mastery_rate}%。",
        mastery_rate=mastery_rate,
        quiz_accuracy=max(0, 100 - min(mistakes * 3, 40)),
        selection_ask_count=selection_ask_count,
        learn_heatmap_summary=learn_heatmap_summary,
        dimensions={
            "mastery_rate": mastery_rate,
            "mistake_count": int(mistakes),
            "focus_minutes": int(focus_minutes),
            "resource_count": len(resources),
            "selection_ask_count": selection_ask_count,
            "learn_evidence_total": learn_heatmap_summary.get("total_evidence", 0),
        },
        strengths=["持续使用学习资源"] if resources else [],
        weaknesses=["部分知识点尚未点亮"] if mastery_rate < 80 else [],
        suggestions=["按学习路径逐步突破薄弱行星", "完成配套练习题巩固"],
    )

    if llm_available():
        prompt = f"""你是 Evaluator Agent，输出学习效果评估 JSON：
{{"summary":"","strengths":[],"weaknesses":[],"suggestions":[]}}
数据：掌握率{mastery_rate}%，错题{int(mistakes)}条，专注{int(focus_minutes)}分钟，资源{len(resources)}份
画像：{getattr(profile, 'summary', '')[:300] if profile else '无'}"""
        raw = await llm_chat(
            [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
            temperature=0.5,
            response_json=True,
        )
        if raw:
            parsed = extract_json(raw)
            if parsed:
                base.summary = parsed.get("summary") or base.summary
                base.strengths = parsed.get("strengths") or base.strengths
                base.weaknesses = parsed.get("weaknesses") or base.weaknesses
                base.suggestions = parsed.get("suggestions") or base.suggestions

    return base


def evaluation_suggestions_for_path(report: EvaluationReportOut) -> List[str]:
    return list(report.suggestions or [])
