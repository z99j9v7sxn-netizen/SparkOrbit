"""练习舱：单题快练（出题 / 语义评分 + STAR 检测 / 历史）。

轻量单 LLM 调用，不属于四模式编排，不写 AgentStep。
"""
from __future__ import annotations

import logging
import random
import re
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mock_interview import InterviewPracticeRecord
from app.services.interview_agents import _chat_json
from app.services.interview_catalog import (
    fallback_questions,
    kind_labels,
    kinds_for,
    role_label,
)
from app.services.interview_scoring import rubric_prompt_block

logger = logging.getLogger(__name__)

_STAR_PATTERNS: dict[str, str] = {
    "situation": r"背景|当时|情境|那个项目|在.{0,6}(公司|团队|课程|比赛)",
    "task": r"任务|目标|需要|负责|要求|指标",
    "action": r"我(做|采取|设计|实现|搭建|优化|推动|组织|分析|排查|沟通)|于是|首先.{0,20}然后",
    "result": r"结果|最终|提升|降低|上线|通过|拿到|数据(显示|表明)|从.{0,8}到",
}


def detect_star(transcript: str) -> dict[str, bool]:
    text = (transcript or "").strip()
    return {key: bool(re.search(pattern, text)) for key, pattern in _STAR_PATTERNS.items()}


def _fallback_question(scenario: str, job_role: str, kind: str) -> dict[str, str]:
    bank = fallback_questions(job_role, 8)
    matched = [q for q in bank if not kind or str(q.get("kind")) == kind]
    src = random.choice(matched or bank)
    return {"kind": str(src.get("kind") or kind or kinds_for(scenario)[0]), "question": str(src.get("question") or "")}


async def generate_practice_question(
    *,
    scenario: str,
    job_role: str,
    kind: str,
    user_id: str,
) -> dict[str, Any]:
    kinds = kinds_for(scenario)
    the_kind = kind if kind in kinds else kinds[0]
    labels = kind_labels(scenario)
    data = await _chat_json(
        "你是面试出题官。出一道口头作答的面试题，30 字以上、无需代码。"
        '严格返回 JSON：{"question":"题目"}',
        (
            f"岗位/场景：{role_label(job_role)}（{scenario}）\n"
            f"考察类型：{labels.get(the_kind, the_kind)}\n"
            "要求：贴合该岗位的真实面试口吻，一次只问一件事。"
        ),
        user_id=user_id,
        endpoint="interview_practice_question",
        temperature=0.7,
    )
    question = str((data or {}).get("question") or "").strip()
    if not question:
        fb = _fallback_question(scenario, job_role, the_kind)
        question = fb["question"]
    return {
        "question": question,
        "kind": the_kind,
        "kind_label": labels.get(the_kind, the_kind),
        "scenario": scenario,
        "job_role": job_role,
        "job_role_label": role_label(job_role),
    }


async def score_practice_answer(
    db: AsyncSession,
    *,
    user_id: str,
    scenario: str,
    job_role: str,
    kind: str,
    question: str,
    transcript: str,
) -> dict[str, Any]:
    text = (transcript or "").strip()
    star = detect_star(text)
    if not text:
        score: float | None = 20.0
        feedback = "没有捕捉到有效回答。建议先在心里列 2-3 个要点再开口。"
        reasons = ["回答为空"]
    else:
        data = await _chat_json(
            (
                "你是面试评分官，对单题口头回答打分。"
                + rubric_prompt_block(scenario)
                + '严格返回 JSON：{"overall":80,"reasons":["扣分理由"],"feedback":"对考生说的、可执行的点评"}'
            ),
            (
                f"岗位：{role_label(job_role)}\n题目：{question}\n回答转写：{text}\n"
                f"STAR 结构检测：{star}（缺失的部分请在点评中提醒）"
            ),
            user_id=user_id,
            endpoint="interview_practice_score",
            temperature=0.25,
        )
        raw_score = (data or {}).get("overall")
        try:
            score = round(max(0.0, min(100.0, float(raw_score))), 1) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None
        if score is None:
            # LLM 不可用时的规则兜底：按长度与 STAR 命中估分
            hits = sum(1 for v in star.values() if v)
            score = round(min(80.0, 35.0 + min(len(text), 400) / 400 * 25 + hits * 5), 1)
        feedback = str((data or {}).get("feedback") or "").strip() or "回答已记录。补上具体数据与结果，说服力会明显提升。"
        reasons = [str(x) for x in ((data or {}).get("reasons") or [])][:5]

    record = InterviewPracticeRecord(
        id=str(uuid4()),
        user_id=user_id,
        scenario=scenario,
        job_role=job_role,
        kind=kind,
        question=question[:2000],
        transcript=text[:4000],
        score=score,
        feedback=feedback[:2000],
        star_hit=star,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return {
        "id": record.id,
        "score": record.score,
        "feedback": record.feedback,
        "star_hit": star,
        "reasons": reasons,
        "created_at": record.created_at.isoformat() if record.created_at else "",
    }


async def list_practice_history(db: AsyncSession, user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(InterviewPracticeRecord)
            .where(InterviewPracticeRecord.user_id == user_id)
            .order_by(InterviewPracticeRecord.created_at.desc())
            .limit(min(max(limit, 1), 50))
        )
    ).scalars().all()
    out: list[dict[str, Any]] = []
    for row in rows:
        labels = kind_labels(row.scenario)
        out.append(
            {
                "id": row.id,
                "scenario": row.scenario,
                "job_role": row.job_role,
                "job_role_label": role_label(row.job_role),
                "kind": row.kind,
                "kind_label": labels.get(row.kind, row.kind),
                "question": row.question,
                "transcript": row.transcript,
                "score": row.score,
                "feedback": row.feedback,
                "star_hit": dict(row.star_hit or {}),
                "created_at": row.created_at.isoformat() if row.created_at else "",
            }
        )
    return out
