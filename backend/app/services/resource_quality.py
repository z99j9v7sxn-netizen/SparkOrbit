"""资源生成质量自动评估（DeepSeek 评判 + 可选重生成标记）。"""
from __future__ import annotations

from typing import Any, Optional

from app.services.llm import extract_json, llm_available, llm_chat


async def score_resource(
    *,
    kind: str,
    title: str,
    content: str,
    planet_name: str,
    planet_slug: str,
    profile_brief: str,
) -> dict[str, Any]:
    """
    返回 quality 字典：
    accuracy / profile_fit / completeness / hallucination_risk (1-5)
    rationale, needs_review, should_retry
    """
    fallback = {
        "accuracy": 3,
        "profile_fit": 3,
        "completeness": 3,
        "hallucination_risk": 2,
        "rationale": "未配置 LLM，使用中性默认分",
        "needs_review": False,
        "should_retry": False,
        "scored_by": "fallback",
    }
    if not llm_available():
        return fallback

    snippet = (content or "")[:3500]
    prompt = f"""你是教育资源质量评判员。对下列 AI 生成学习资源打分（整数 1-5），只输出 JSON：
{{
  "accuracy":1-5,
  "profile_fit":1-5,
  "completeness":1-5,
  "hallucination_risk":1-5,
  "rationale":"一句话依据"
}}
规则：accuracy=知识准确性；profile_fit=与学生画像贴合；completeness=结构完整可用；
hallucination_risk=幻觉/跑题风险（越高越危险）。
知识点：{planet_name}（{planet_slug}）
类型：{kind}
标题：{title}
画像：{profile_brief[:400]}
内容：
{snippet}
"""
    raw = await llm_chat(
        [{"role": "system", "content": "只输出 JSON。"}, {"role": "user", "content": prompt}],
        temperature=0.2,
        response_json=True,
        timeout=25.0,
        endpoint="resource_quality",
    )
    if not raw:
        return fallback
    parsed = extract_json(raw)
    if not isinstance(parsed, dict):
        return fallback

    def _clamp(v: Any, default: int = 3) -> int:
        try:
            return max(1, min(5, int(v)))
        except (TypeError, ValueError):
            return default

    accuracy = _clamp(parsed.get("accuracy"))
    profile_fit = _clamp(parsed.get("profile_fit"))
    completeness = _clamp(parsed.get("completeness"))
    hallu = _clamp(parsed.get("hallucination_risk"), 2)
    should_retry = accuracy < 3 or profile_fit < 3 or completeness < 3 or hallu >= 4
    needs_review = should_retry
    return {
        "accuracy": accuracy,
        "profile_fit": profile_fit,
        "completeness": completeness,
        "hallucination_risk": hallu,
        "rationale": str(parsed.get("rationale") or "")[:200],
        "needs_review": needs_review,
        "should_retry": should_retry,
        "scored_by": "deepseek",
    }


def quality_summary(q: Optional[dict]) -> str:
    if not q:
        return ""
    return (
        f"A{q.get('accuracy')}/P{q.get('profile_fit')}/C{q.get('completeness')}/H{q.get('hallucination_risk')}"
        f"{' · 待复核' if q.get('needs_review') else ''}"
    )
