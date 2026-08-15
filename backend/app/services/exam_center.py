"""考级中心：AI 题库 / 模考评分 / 词书 / 精听材料 / 写译批改 / 21 天挑战。"""
from __future__ import annotations

import json
import logging
import random
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exam import (
    ChallengeCampaignRecord,
    ExamMockRun,
    ExamPaper,
    ExamPracticeLog,
    ExamQuestion,
    ExamWordEntry,
)
from app.models.user import User
from app.services.llm import extract_json, extract_json_list, llm_chat

logger = logging.getLogger(__name__)

EXAM_LABELS = {
    "cet4": "大学英语四级（CET-4）",
    "cet6": "大学英语六级（CET-6）",
    "ielts": "雅思（IELTS）",
    "cantonese": "粤语水平测试",
}

SECTION_LABELS = {
    "listening": "听力理解",
    "reading": "阅读理解",
    "cloze": "选词填空",
    "translation": "翻译",
    "writing": "写作",
    "vocab": "词汇",
}

OBJECTIVE_SECTIONS = {"listening", "reading", "cloze", "vocab"}
SUBJECTIVE_SECTIONS = {"translation", "writing"}

# 模考卷结构：各题型题量
MOCK_STRUCTURE = [
    ("listening", 5),
    ("reading", 5),
    ("cloze", 5),
    ("translation", 1),
    ("writing", 1),
]

CHECKIN_DAILY_ITEMS = 10  # 每日打卡目标：完成学习条目数（做题+单词）
CHECKIN_POINTS = 10
CHECKIN_FINISH_BONUS = 100


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day_start() -> datetime:
    return _now().replace(hour=0, minute=0, second=0, microsecond=0)


def _exam_label(exam_type: str) -> str:
    return EXAM_LABELS.get(exam_type, exam_type)


def _question_out(q: ExamQuestion, *, with_answer: bool = False) -> dict[str, Any]:
    out = {
        "id": q.id,
        "exam_type": q.exam_type,
        "section": q.section,
        "question": q.question,
        "options": q.options or {},
        "audio_text": q.audio_text or "",
        "difficulty": q.difficulty,
        "source": q.source,
    }
    if with_answer:
        out["answer"] = q.answer
        out["analysis"] = q.analysis
    return out


# ---------------- 题库生成 / 导入 ----------------


async def generate_questions(
    session: AsyncSession,
    exam_type: str,
    section: str,
    count: int = 5,
    created_by: str = "",
) -> list[ExamQuestion]:
    """LLM 批量生成模拟题入库。"""
    count = max(1, min(count, 10))
    label = _exam_label(exam_type)
    sec_label = SECTION_LABELS.get(section, section)

    if section == "listening":
        shape = (
            '{"audio_text":"一段 60-100 词的英文听力材料（对话或短文）",'
            '"question":"针对材料的英文问题","options":{"A":"...","B":"...","C":"...","D":"..."},'
            '"answer":"A","analysis":"中文解析"}'
        )
    elif section in ("reading", "cloze", "vocab"):
        shape = (
            '{"question":"题干（阅读题含短文原文；选词填空含挖空句；词汇题为词义辨析）",'
            '"options":{"A":"...","B":"...","C":"...","D":"..."},'
            '"answer":"A","analysis":"中文解析，说明正确项依据与干扰项问题"}'
        )
    elif section == "translation":
        shape = '{"question":"一段 60-100 字的中文段落，要求译成英文","answer":"参考译文","analysis":"翻译要点（得分点）"}'
    else:  # writing
        shape = '{"question":"作文题目与要求（含字数要求）","answer":"高分范文","analysis":"写作思路与得分点"}'

    if exam_type == "cantonese":
        extra_rule = "考试语言为粤语（繁体字表述题干与选项），解析用简体中文。"
    else:
        extra_rule = "题目语言与真实考试一致（英文题干与选项），解析用简体中文。"

    system = (
        f"你是{label}命题专家。生成 {count} 道「{sec_label}」高质量模拟题，风格、难度、题型与真实考试一致。"
        f"{extra_rule}"
        f'严格返回 JSON：{{"questions":[{shape}]}}。不得输出多余文本。'
    )
    raw = await llm_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": f"生成 {count} 道题"}],
        temperature=0.75,
        response_json=True,
        timeout=120.0,
    )
    items = extract_json_list(raw or "") or []
    rows: list[ExamQuestion] = []
    for item in items[:count]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if not question:
            continue
        options = item.get("options") if isinstance(item.get("options"), dict) else {}
        rows.append(
            ExamQuestion(
                exam_type=exam_type,
                section=section,
                question=question,
                options=options,
                answer=str(item.get("answer") or "").strip(),
                analysis=str(item.get("analysis") or "").strip(),
                audio_text=str(item.get("audio_text") or "").strip(),
                source="ai",
                created_by=created_by,
            )
        )
    if not rows:
        raise RuntimeError("题目生成失败，请稍后重试")
    session.add_all(rows)
    await session.commit()
    for r in rows:
        await session.refresh(r)
    return rows


async def import_questions_from_text(
    session: AsyncSession,
    exam_type: str,
    text: str,
    created_by: str = "",
) -> list[ExamQuestion]:
    """从题源文本（PDF 解析结果）结构化导入题目。"""
    snippet = (text or "").strip()[:12000]
    if len(snippet) < 30:
        raise ValueError("题源文本过短，无法解析")
    system = (
        f"你是{_exam_label(exam_type)}题库编辑。从给定文本中提取全部题目并结构化。"
        "每题输出：section（listening/reading/cloze/translation/writing/vocab 之一）、"
        "question（题干，阅读题含原文）、options（客观题 A-D 选项对象，主观题为空对象）、"
        "answer（答案）、analysis（解析，缺失则留空）。"
        '严格返回 JSON：{"questions":[...]}'
    )
    raw = await llm_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": snippet}],
        temperature=0.2,
        response_json=True,
        timeout=180.0,
    )
    items = extract_json_list(raw or "") or []
    rows: list[ExamQuestion] = []
    for item in items[:50]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        section = str(item.get("section") or "").strip()
        if not question or section not in SECTION_LABELS:
            continue
        options = item.get("options") if isinstance(item.get("options"), dict) else {}
        rows.append(
            ExamQuestion(
                exam_type=exam_type,
                section=section,
                question=question,
                options=options,
                answer=str(item.get("answer") or "").strip(),
                analysis=str(item.get("analysis") or "").strip(),
                source="import",
                created_by=created_by,
            )
        )
    if not rows:
        raise ValueError("未能从文本中解析出题目")
    session.add_all(rows)
    await session.commit()
    return rows


async def bank_summary(session: AsyncSession, exam_type: str) -> dict[str, Any]:
    rows = (
        await session.execute(
            select(ExamQuestion.section, sa_func.count(ExamQuestion.id))
            .where(ExamQuestion.exam_type == exam_type)
            .group_by(ExamQuestion.section)
        )
    ).all()
    return {"exam_type": exam_type, "sections": {sec: int(cnt) for sec, cnt in rows}}


# ---------------- 专项刷题 ----------------


async def pick_questions(
    session: AsyncSession,
    exam_type: str,
    section: str,
    count: int,
    *,
    created_by: str = "",
    auto_generate: bool = True,
) -> list[ExamQuestion]:
    """从题库随机抽题；不足时自动 AI 补题。"""
    ids = (
        (
            await session.execute(
                select(ExamQuestion.id).where(
                    ExamQuestion.exam_type == exam_type, ExamQuestion.section == section
                )
            )
        )
        .scalars()
        .all()
    )
    if len(ids) < count and auto_generate:
        try:
            await generate_questions(
                session, exam_type, section, count=max(count - len(ids), 3), created_by=created_by
            )
            ids = (
                (
                    await session.execute(
                        select(ExamQuestion.id).where(
                            ExamQuestion.exam_type == exam_type, ExamQuestion.section == section
                        )
                    )
                )
                .scalars()
                .all()
            )
        except Exception:  # noqa: BLE001
            logger.exception("auto generate questions failed: %s/%s", exam_type, section)
    if not ids:
        return []
    chosen = random.sample(list(ids), min(count, len(ids)))
    rows = (
        (await session.execute(select(ExamQuestion).where(ExamQuestion.id.in_(chosen)))).scalars().all()
    )
    return list(rows)


async def check_answer(
    session: AsyncSession, user: User, question_id: str, answer: str
) -> dict[str, Any]:
    q = (
        await session.execute(select(ExamQuestion).where(ExamQuestion.id == question_id))
    ).scalar_one_or_none()
    if q is None:
        raise LookupError("题目不存在")
    if q.section in OBJECTIVE_SECTIONS:
        correct = (answer or "").strip().upper() == (q.answer or "").strip().upper()
    else:
        correct = bool((answer or "").strip())
    return {
        "ok": True,
        "correct": correct,
        "answer": q.answer,
        "analysis": q.analysis,
        "question": _question_out(q, with_answer=True),
    }


async def log_practice(
    session: AsyncSession,
    user_id: str,
    *,
    exam_type: str,
    section: str,
    activity: str,
    total: int,
    correct: int,
    meta: dict | None = None,
) -> None:
    session.add(
        ExamPracticeLog(
            user_id=user_id,
            exam_type=exam_type,
            section=section,
            activity=activity,
            total=max(0, int(total)),
            correct=max(0, int(correct)),
            meta_json=meta or {},
        )
    )
    await session.commit()


# ---------------- 整套模考 ----------------


async def start_mock(
    session: AsyncSession, user: User, exam_type: str
) -> dict[str, Any]:
    structure: list[dict[str, Any]] = []
    all_questions: list[dict[str, Any]] = []
    for section, count in MOCK_STRUCTURE:
        rows = await pick_questions(
            session, exam_type, section, count, created_by=user.id, auto_generate=True
        )
        if not rows:
            continue
        structure.append({"section": section, "question_ids": [r.id for r in rows]})
        all_questions.extend(_question_out(r) for r in rows)
    if not all_questions:
        raise RuntimeError("题库为空且自动补题失败，请稍后重试")

    paper = ExamPaper(
        exam_type=exam_type,
        title=f"{_exam_label(exam_type)} 全真模拟卷",
        structure=structure,
        duration_minutes=60,
        source="ai",
    )
    session.add(paper)
    await session.flush()
    run = ExamMockRun(user_id=user.id, paper_id=paper.id, exam_type=exam_type, status="ongoing")
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return {
        "run_id": run.id,
        "paper_id": paper.id,
        "title": paper.title,
        "duration_minutes": paper.duration_minutes,
        "structure": structure,
        "questions": all_questions,
    }


async def submit_mock(
    session: AsyncSession, user: User, run_id: str, answers: dict[str, str]
) -> dict[str, Any]:
    run = (
        await session.execute(
            select(ExamMockRun).where(ExamMockRun.id == run_id, ExamMockRun.user_id == user.id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise LookupError("模考记录不存在")
    paper = (
        await session.execute(select(ExamPaper).where(ExamPaper.id == run.paper_id))
    ).scalar_one_or_none()
    if paper is None:
        raise LookupError("试卷不存在")

    qids: list[str] = []
    for block in paper.structure or []:
        qids.extend(block.get("question_ids") or [])
    questions = (
        (await session.execute(select(ExamQuestion).where(ExamQuestion.id.in_(qids)))).scalars().all()
    )
    qmap = {q.id: q for q in questions}

    section_scores: dict[str, dict[str, Any]] = {}
    detail: list[dict[str, Any]] = []
    wrong_objective: list[ExamQuestion] = []
    earned = 0.0
    total_weight = 0.0

    for block in paper.structure or []:
        section = block.get("section") or ""
        stats = section_scores.setdefault(section, {"total": 0, "correct": 0, "score": 0.0})
        for qid in block.get("question_ids") or []:
            q = qmap.get(qid)
            if q is None:
                continue
            ans = str(answers.get(qid) or "").strip()
            stats["total"] += 1
            total_weight += 1.0
            if q.section in OBJECTIVE_SECTIONS:
                correct = bool(ans) and ans.upper() == (q.answer or "").strip().upper()
                if correct:
                    stats["correct"] += 1
                    stats["score"] += 1.0
                    earned += 1.0
                else:
                    wrong_objective.append(q)
                detail.append(
                    {
                        "question_id": qid,
                        "section": section,
                        "correct": correct,
                        "my_answer": ans,
                        "answer": q.answer,
                        "analysis": q.analysis,
                    }
                )
            else:
                ratio, feedback = await _grade_subjective(q, ans)
                stats["correct"] += 1 if ratio >= 0.6 else 0
                stats["score"] += ratio
                earned += ratio
                detail.append(
                    {
                        "question_id": qid,
                        "section": section,
                        "correct": ratio >= 0.6,
                        "my_answer": ans,
                        "answer": q.answer,
                        "analysis": feedback or q.analysis,
                        "ratio": round(ratio, 2),
                    }
                )

    score = round(earned / total_weight * 100, 1) if total_weight else 0.0
    run.answers = answers
    run.score = score
    run.section_scores = section_scores
    run.status = "done"
    run.finished_at = _now()
    session.add(run)

    # 客观错题自动归档进错题本（进入 SRS 复习队列）
    archived = 0
    try:
        from app.models.zone_extras import MistakeRecord

        for q in wrong_objective[:10]:
            opts = "\n".join(f"{k}. {v}" for k, v in (q.options or {}).items())
            session.add(
                MistakeRecord(
                    user_id=user.id,
                    question=(q.question + ("\n" + opts if opts else ""))[:2000],
                    student_answer=str(answers.get(q.id) or ""),
                    correct_answer=q.answer,
                    subject=_exam_label(run.exam_type),
                    note=q.analysis[:500] if q.analysis else "",
                )
            )
            archived += 1
    except Exception:  # noqa: BLE001
        logger.exception("archive mock mistakes failed")

    await session.commit()
    try:
        await log_practice(
            session,
            user.id,
            exam_type=run.exam_type,
            section="mock",
            activity="practice",
            total=int(total_weight),
            correct=int(earned),
            meta={"run_id": run.id, "score": score},
        )
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "run_id": run.id,
        "score": score,
        "section_scores": section_scores,
        "detail": detail,
        "mistakes_archived": archived,
    }


async def _grade_subjective(q: ExamQuestion, answer: str) -> tuple[float, str]:
    """主观题（翻译/写作）快速评分，返回 (得分比例 0-1, 简评)。"""
    if not (answer or "").strip():
        return 0.0, "未作答"
    system = (
        "你是阅卷老师。对考生作答按 0-100 打分并给一句话中文点评。"
        '严格返回 JSON：{"score":75,"comment":"..."}'
    )
    user_msg = f"题目：{q.question}\n参考答案：{q.answer}\n考生作答：{answer[:2000]}"
    try:
        raw = await llm_chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
            temperature=0.2,
            response_json=True,
            timeout=60.0,
        )
        obj = extract_json(raw or "") or {}
        score = float(obj.get("score") or 0)
        return max(0.0, min(score, 100.0)) / 100.0, str(obj.get("comment") or "")
    except Exception:  # noqa: BLE001
        logger.exception("subjective grading failed")
        return 0.5, "自动评分暂不可用，按 50% 计"


# ---------------- 写作 / 翻译批改 ----------------


async def grade_essay(
    user_id: str, exam_type: str, kind: str, prompt: str, text: str
) -> dict[str, Any]:
    """写作/翻译精细批改：分维度评分 + 逐句润色。"""
    body = (text or "").strip()
    if len(body) < 10:
        raise ValueError("提交内容过短")
    kind_label = "写作" if kind == "writing" else "翻译"
    system = (
        f"你是{_exam_label(exam_type)}{kind_label}阅卷专家。按考试评分标准批改。"
        "严格返回 JSON："
        '{"score":78,"dimensions":[{"name":"内容切题","score":80,"comment":"..."},'
        '{"name":"结构组织","score":75,"comment":"..."},{"name":"语言表达","score":76,"comment":"..."},'
        '{"name":"词汇语法","score":80,"comment":"..."}],'
        '"sentence_feedback":[{"original":"原句","revised":"润色后","reason":"中文说明"}],'
        '"highlights":["值得保留的亮点表达"],"suggestions":["提升建议"]}'
        "sentence_feedback 最多 6 条，优先修改问题最大的句子。"
    )
    user_msg = f"题目/要求：{prompt or '（未提供）'}\n\n考生{kind_label}：\n{body[:4000]}"
    raw = await llm_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user_msg}],
        temperature=0.3,
        response_json=True,
        timeout=120.0,
        user_id=user_id,
        endpoint="exam_essay_grade",
    )
    obj = extract_json(raw or "")
    if not isinstance(obj, dict) or "score" not in obj:
        raise RuntimeError("批改失败，请稍后重试")
    obj["ok"] = True
    return obj


# ---------------- 听力精听材料 ----------------


async def generate_listening_material(
    user_id: str, exam_type: str, topic: str = ""
) -> dict[str, Any]:
    """生成精听材料：短文 + 分句 + 听写挖空。前端用 /api/tts 合成音频。"""
    lang_rule = "粤语口语（繁体字）" if exam_type == "cantonese" else "英文"
    system = (
        f"你是{_exam_label(exam_type)}听力教练。生成一段 80-120 词的{lang_rule}听力短文，"
        "接近真实考试的语速文本与题材。"
        "严格返回 JSON："
        '{"title":"标题","transcript":"完整原文","sentences":["按句切分的原文数组"],'
        '"blanks":[{"sentence_index":0,"word":"挖空的关键词"}],'
        '"translation":"全文中文翻译"}'
        "blanks 选 4-6 个信息量大的实词。"
    )
    raw = await llm_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"题材偏好：{topic or '校园/生活/科普任选'}"},
        ],
        temperature=0.7,
        response_json=True,
        timeout=90.0,
        user_id=user_id,
        endpoint="exam_listening",
    )
    obj = extract_json(raw or "")
    if not isinstance(obj, dict) or not obj.get("transcript"):
        raise RuntimeError("听力材料生成失败，请稍后重试")
    obj["ok"] = True
    return obj


# ---------------- 词书 ----------------


async def list_words(
    session: AsyncSession, exam_type: str, offset: int = 0, limit: int = 20
) -> dict[str, Any]:
    total = (
        await session.execute(
            select(sa_func.count(ExamWordEntry.id)).where(ExamWordEntry.exam_type == exam_type)
        )
    ).scalar_one()
    rows = (
        (
            await session.execute(
                select(ExamWordEntry)
                .where(ExamWordEntry.exam_type == exam_type)
                .order_by(ExamWordEntry.freq_rank.asc(), ExamWordEntry.created_at.asc())
                .offset(max(0, offset))
                .limit(max(1, min(limit, 50)))
            )
        )
        .scalars()
        .all()
    )
    return {
        "total": int(total),
        "words": [
            {
                "id": w.id,
                "word": w.word,
                "phonetic": w.phonetic,
                "meaning": w.meaning,
                "example": w.example,
                "freq_rank": w.freq_rank,
            }
            for w in rows
        ],
    }


async def seed_words(session: AsyncSession, exam_type: str, count: int = 30) -> int:
    """AI 生成一批高频词入词书（按频次段递增，避免重复）。"""
    count = max(10, min(count, 40))
    existing = (
        (
            await session.execute(
                select(ExamWordEntry.word).where(ExamWordEntry.exam_type == exam_type)
            )
        )
        .scalars()
        .all()
    )
    existing_set = {w.lower() for w in existing}
    start_rank = len(existing)
    lang_rule = (
        "输出粤语常用词（繁体字），phonetic 用粤拼" if exam_type == "cantonese" else "输出英文单词，phonetic 用国际音标"
    )
    system = (
        f"你是{_exam_label(exam_type)}词汇专家。给出第 {start_rank + 1} 到 {start_rank + count} 高频的核心考纲词。"
        f"{lang_rule}。每词配简明中文释义与一条真题风格例句。"
        '严格返回 JSON：{"words":[{"word":"...","phonetic":"...","meaning":"...","example":"..."}]}'
    )
    raw = await llm_chat(
        [{"role": "system", "content": system}, {"role": "user", "content": f"生成 {count} 个词"}],
        temperature=0.5,
        response_json=True,
        timeout=120.0,
    )
    obj = extract_json(raw or "") or {}
    items = obj.get("words") if isinstance(obj.get("words"), list) else []
    added = 0
    for i, item in enumerate(items[:count]):
        if not isinstance(item, dict):
            continue
        word = str(item.get("word") or "").strip()
        if not word or word.lower() in existing_set:
            continue
        session.add(
            ExamWordEntry(
                exam_type=exam_type,
                word=word,
                phonetic=str(item.get("phonetic") or "").strip(),
                meaning=str(item.get("meaning") or "").strip(),
                example=str(item.get("example") or "").strip(),
                freq_rank=start_rank + added + 1,
            )
        )
        existing_set.add(word.lower())
        added += 1
    if added:
        await session.commit()
    return added


async def collect_word(session: AsyncSession, user_id: str, word_id: str) -> dict[str, Any]:
    """把词书条目加入个人复习队列（ReviewCard kind=word）。"""
    from app.services.review_queue import add_review_card

    w = (
        await session.execute(select(ExamWordEntry).where(ExamWordEntry.id == word_id))
    ).scalar_one_or_none()
    if w is None:
        raise LookupError("词条不存在")
    row = await add_review_card(
        session,
        user_id,
        kind="word",
        front=w.word,
        back=w.meaning,
        extra=json.dumps({"phonetic": w.phonetic, "example": w.example}, ensure_ascii=False),
        source_id=f"exam_word:{w.id}",
    )
    return {"ok": True, "card_id": row.id}


# ---------------- 21 天打卡挑战 ----------------


async def get_or_create_campaign(
    session: AsyncSession, user: User, exam_type: str = "cet4", create: bool = False
) -> ChallengeCampaignRecord | None:
    row = (
        (
            await session.execute(
                select(ChallengeCampaignRecord)
                .where(
                    ChallengeCampaignRecord.user_id == user.id,
                    ChallengeCampaignRecord.status == "active",
                )
                .order_by(ChallengeCampaignRecord.started_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if row is None and create:
        row = ChallengeCampaignRecord(
            user_id=user.id,
            exam_type=exam_type,
            daily_goal={"items": CHECKIN_DAILY_ITEMS},
            checkins=[],
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return row


async def _today_progress(session: AsyncSession, user_id: str) -> int:
    """今日完成学习条目数（刷题/词汇训练/复习提交都写 ExamPracticeLog）。"""
    day_start = _day_start()
    practice = (
        await session.execute(
            select(sa_func.coalesce(sa_func.sum(ExamPracticeLog.total), 0)).where(
                ExamPracticeLog.user_id == user_id, ExamPracticeLog.created_at >= day_start
            )
        )
    ).scalar_one()
    return int(practice)


async def campaign_status(session: AsyncSession, user: User) -> dict[str, Any]:
    row = await get_or_create_campaign(session, user, create=False)
    if row is None:
        return {"active": False}
    today = _now().date().isoformat()
    progress = await _today_progress(session, user.id)
    goal = int((row.daily_goal or {}).get("items") or CHECKIN_DAILY_ITEMS)
    return {
        "active": True,
        "id": row.id,
        "name": row.name,
        "exam_type": row.exam_type,
        "days_total": row.days_total,
        "days_done": len(row.checkins or []),
        "checkins": row.checkins or [],
        "checked_today": today in (row.checkins or []),
        "today_progress": progress,
        "today_goal": goal,
        "can_checkin": progress >= goal and today not in (row.checkins or []),
    }


async def campaign_checkin(session: AsyncSession, user: User) -> dict[str, Any]:
    row = await get_or_create_campaign(session, user, create=False)
    if row is None:
        raise LookupError("尚未加入挑战")
    today = _now().date().isoformat()
    checkins = list(row.checkins or [])
    if today in checkins:
        return {"ok": True, "already": True, "days_done": len(checkins)}
    progress = await _today_progress(session, user.id)
    goal = int((row.daily_goal or {}).get("items") or CHECKIN_DAILY_ITEMS)
    if progress < goal:
        raise ValueError(f"今日进度 {progress}/{goal}，先完成学习任务再打卡")

    checkins.append(today)
    row.checkins = checkins
    bonus = CHECKIN_POINTS
    finished = len(checkins) >= row.days_total
    if finished:
        row.status = "done"
        row.finished_at = _now()
        bonus += CHECKIN_FINISH_BONUS
    user.points += bonus
    session.add_all([row, user])
    await session.commit()
    return {
        "ok": True,
        "days_done": len(checkins),
        "finished": finished,
        "points_earned": bonus,
        "points": user.points,
    }
