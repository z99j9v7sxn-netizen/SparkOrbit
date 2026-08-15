"""判题侧独立引用与逻辑矛盾检测（防幻觉硬互锁）。"""
from __future__ import annotations

from typing import Any

from app.services.llm import extract_json, llm_available, llm_chat


async def evaluate_submission_consistency(
    *,
    planet_slug: str,
    planet_name: str,
    question: str,
    answer_key: str,
    selected_key: str,
    explanation: str,
    expected_key_points: list[str],
    rule_correct: bool,
) -> dict[str, Any]:
    """
    Evaluator 独立产出 cited_knowledge_point_id / confidence / contradiction。
    不直接抄 Teacher 的 knowledge_point_id。
    """
    default = {
        "cited_knowledge_point_id": planet_slug,
        "confidence": 0.85 if rule_correct else 0.65,
        "contradiction": False,
        "reason": "",
        "evaluator_correct": rule_correct,
    }
    if not llm_available():
        return default

    prompt = f"""你是 Evaluator Agent。根据题目与标答，独立判断学生作答并做引用一致性检查。
只输出 JSON：
{{
  "cited_knowledge_point_id": "你认为本题实际考察的知识点 slug",
  "evaluator_correct": true/false,
  "confidence": 0.0-1.0,
  "contradiction": true/false,
  "reason": "一句话"
}}
规则：
- cited_knowledge_point_id 必须是你独立判断的考察点；若认为跑题可填其他 slug，但应尽量贴近给定行星。
- 若标答解释与 answer_key 逻辑矛盾，或你判定对错与规则对错冲突，设 contradiction=true 并降低 confidence。
- expected_key_points 应被覆盖。

给定行星 slug：{planet_slug}
行星名称：{planet_name}
题干：{question}
标准答案键：{answer_key}
学生选择：{selected_key}
题目解析：{explanation[:400]}
期望要点：{expected_key_points}
规则引擎判定 correct={rule_correct}
"""
    raw = await llm_chat(
        [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
        temperature=0.2,
        response_json=True,
    )
    if not raw:
        return default
    parsed = extract_json(raw)
    if not isinstance(parsed, dict):
        return default

    cited = str(parsed.get("cited_knowledge_point_id") or planet_slug).strip() or planet_slug
    try:
        conf = float(parsed.get("confidence", default["confidence"]))
    except (TypeError, ValueError):
        conf = default["confidence"]
    conf = max(0.0, min(1.0, conf))
    contradiction = bool(parsed.get("contradiction"))
    evaluator_correct = bool(parsed.get("evaluator_correct", rule_correct))
    if evaluator_correct != rule_correct:
        contradiction = True
        conf = min(conf, 0.4)
    if cited != planet_slug:
        conf = min(conf, 0.4)
        contradiction = True
    return {
        "cited_knowledge_point_id": cited,
        "confidence": conf,
        "contradiction": contradiction,
        "reason": str(parsed.get("reason") or "")[:200],
        "evaluator_correct": evaluator_correct,
    }
