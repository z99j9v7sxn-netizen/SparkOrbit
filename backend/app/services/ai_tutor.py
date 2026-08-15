"""AI 批改与举一反三。"""
import json
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_task import AiTaskRecord
from app.models.user import User
from app.schemas.ai_tutor import (
    GradeItemResult,
    GradeRequest,
    GradeResponse,
    SimilarQuestionItem,
    SimilarQuestionsRequest,
    SimilarQuestionsResponse,
)
from app.services.llm import extract_json, llm_available, llm_chat

logger = logging.getLogger(__name__)

SIMILAR_SYSTEM = """你是 SparkOrbit 的出题助手。根据用户提供的原题，生成同知识点、同难度梯度的变式题。
严格返回 JSON，不要 Markdown：
{
  "items": [
    {
      "question": "题目正文",
      "answer": "标准答案",
      "explanation": "详细解析，含关键步骤与易错点",
      "difficulty": "easy|medium|hard"
    }
  ]
}"""

GRADE_SYSTEM = """你是 SparkOrbit 的批改助手。逐题对比学生答案与参考答案，给出 0-100 分、是否正确、反馈与改进建议。
严格返回 JSON，不要 Markdown：
{
  "items": [
    {
      "question": "原题",
      "student_answer": "学生答案",
      "score": 85,
      "is_correct": true,
      "feedback": "批改反馈",
      "suggestion": "改进建议"
    }
  ],
  "summary": "整体总结"
}"""


def _fallback_similar(req: SimilarQuestionsRequest) -> SimilarQuestionsResponse:
    items = []
    for i in range(req.count):
        items.append(
            SimilarQuestionItem(
                question=f"【变式 {i + 1}】基于「{req.source_question[:40]}...」的同知识点练习题：请写出核心思路并给出结论。",
                answer="请参考原题知识框架，结合具体条件求解。",
                explanation="本题为离线兜底变式题。配置 DeepSeek 后将生成更精准的同类题与详解。",
                difficulty="medium",
            )
        )
    return SimilarQuestionsResponse(source_question=req.source_question, items=items, fallback=True)


def _fallback_grade(req: GradeRequest) -> GradeResponse:
    items: list[GradeItemResult] = []
    for item in req.items:
        ok = item.student_answer.strip().lower() == item.reference_answer.strip().lower()
        items.append(
            GradeItemResult(
                question=item.question,
                student_answer=item.student_answer,
                score=100 if ok else 40,
                is_correct=ok,
                feedback="离线兜底批改：仅做简单文本匹配，建议配置 DeepSeek 获取智能批改。",
                suggestion="完善关键步骤与术语表述。",
            )
        )
    total = sum(x.score for x in items)
    return GradeResponse(
        total_score=total,
        max_score=len(items) * 100,
        items=items,
        summary="离线兜底批改完成。",
        fallback=True,
    )


async def generate_similar_questions(
    session: AsyncSession,
    user: User,
    req: SimilarQuestionsRequest,
) -> SimilarQuestionsResponse:
    if not llm_available():
        result = _fallback_similar(req)
    else:
        user_prompt = (
            f"原题：{req.source_question}\n"
            f"学科/主题：{req.subject or '通用'}\n"
            f"请生成 {req.count} 道举一反三变式题。"
        )
        content = await llm_chat(
            [{"role": "system", "content": SIMILAR_SYSTEM}, {"role": "user", "content": user_prompt}],
            temperature=0.65,
            response_json=True,
        )
        data = extract_json(content) if content else None
        if not data or not data.get("items"):
            result = _fallback_similar(req)
        else:
            items = [
                SimilarQuestionItem(
                    question=str(it.get("question", "")),
                    answer=str(it.get("answer", "")),
                    explanation=str(it.get("explanation", "")),
                    difficulty=str(it.get("difficulty", "medium")),
                )
                for it in data["items"][: req.count]
            ]
            result = SimilarQuestionsResponse(source_question=req.source_question, items=items, fallback=False)

    session.add(
        AiTaskRecord(
            id=str(uuid4()),
            user_id=user.id,
            task_type="similar",
            input_text=req.source_question,
            result_json=json.loads(result.model_dump_json()),
        )
    )
    await session.commit()
    return result


async def grade_answers(session: AsyncSession, user: User, req: GradeRequest) -> GradeResponse:
    if not llm_available():
        result = _fallback_grade(req)
    else:
        payload = json.dumps([it.model_dump() for it in req.items], ensure_ascii=False)
        content = await llm_chat(
            [{"role": "system", "content": GRADE_SYSTEM}, {"role": "user", "content": payload}],
            temperature=0.3,
            response_json=True,
        )
        data = extract_json(content) if content else None
        if not data or not data.get("items"):
            result = _fallback_grade(req)
        else:
            items = [
                GradeItemResult(
                    question=str(it.get("question", "")),
                    student_answer=str(it.get("student_answer", "")),
                    score=max(0, min(100, int(it.get("score", 0)))),
                    is_correct=bool(it.get("is_correct", False)),
                    feedback=str(it.get("feedback", "")),
                    suggestion=str(it.get("suggestion", "")),
                )
                for it in data["items"]
            ]
            total = sum(x.score for x in items)
            result = GradeResponse(
                total_score=total,
                max_score=len(items) * 100,
                items=items,
                summary=str(data.get("summary", "")),
                fallback=False,
            )

    session.add(
        AiTaskRecord(
            id=str(uuid4()),
            user_id=user.id,
            task_type="grade",
            input_text=json.dumps([it.model_dump() for it in req.items], ensure_ascii=False)[:8000],
            result_json=json.loads(result.model_dump_json()),
        )
    )
    await session.commit()
    return result
