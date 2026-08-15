"""模拟面试评分：维度集、rubric 锚定、语速/停顿/填充词、缺模态归一化融合。"""
from __future__ import annotations

import asyncio
import re
from typing import Any

JOB_DIMENSIONS: list[tuple[str, str]] = [
    ("professional_knowledge", "专业知识"),
    ("job_skill_match", "岗位匹配"),
    ("language_expression", "语言表达"),
    ("logical_thinking", "逻辑思维"),
    ("stress_resistance", "抗压应变"),
]

ACADEMIC_DIMENSIONS: list[tuple[str, str]] = [
    ("subject_depth", "学科深度"),
    ("major_fit", "专业匹配"),
    ("expression_clarity", "表达条理"),
    ("rigor", "思维严谨"),
    ("academic_potential", "学术潜质"),
]

SEMANTIC_WEIGHT = 0.70
PROSODY_WEIGHT = 0.15
VISUAL_WEIGHT = 0.15

FILLER_PATTERNS = (
    "嗯+",
    "啊+",
    "呃+",
    "那个",
    "就是说?",
    "然后",
    "怎么说",
    "um+",
    "uh+",
    "like",
    "you know",
)

RUBRIC: dict[str, dict[str, str]] = {
    "professional_knowledge": {
        "90": "要点完整，能讲清原理并给出量化或反例",
        "75": "要点基本覆盖，但缺一层深度或例子",
        "60": "只答到表面关键词，缺少机制",
        "40": "跑题、明显错误或几乎没有实质内容",
    },
    "job_skill_match": {
        "90": "经历与岗位要求一一对应，能量化贡献",
        "75": "相关经历能对上，但匹配点偏少",
        "60": "经历泛泛，岗位关联弱",
        "40": "与目标岗位几乎无关",
    },
    "language_expression": {
        "90": "表达流畅、用词准确、少填充词",
        "75": "能听懂，偶有重复或口头禅",
        "60": "停顿多、结构松散",
        "40": "难以成句或大量填充词",
    },
    "logical_thinking": {
        "90": "结论先行、层次清楚，能用 STAR 或因果链",
        "75": "有结构但过渡生硬",
        "60": "想到哪说到哪",
        "40": "前后矛盾或无法展开",
    },
    "stress_resistance": {
        "90": "面对追问仍能稳住并补充证据",
        "75": "略紧张但仍能回答",
        "60": "回避或反复同一句话",
        "40": "卡死、放弃或情绪失控",
    },
    "subject_depth": {
        "90": "能讲清定义、边界与典型误区",
        "75": "概念正确但缺推导",
        "60": "只能复述名词",
        "40": "概念错误",
    },
    "major_fit": {
        "90": "研究方向/课程与报考方向高度吻合",
        "75": "大体相关",
        "60": "关联牵强",
        "40": "几乎不匹配",
    },
    "expression_clarity": {
        "90": "条理清楚、术语使用准确",
        "75": "能讲明白，偶有跳跃",
        "60": "结构松散",
        "40": "表达混乱",
    },
    "rigor": {
        "90": "有假设、限定条件与反例意识",
        "75": "推理基本成立",
        "60": "凭感觉作答",
        "40": "自相矛盾",
    },
    "academic_potential": {
        "90": "能提出可验证的下一步问题",
        "75": "有求知欲但缺方法",
        "60": "停留在应试记忆",
        "40": "无研究意识",
    },
}


def dimensions_for(scenario: str) -> list[tuple[str, str]]:
    return list(ACADEMIC_DIMENSIONS if scenario == "academic" else JOB_DIMENSIONS)


def dimension_labels(scenario: str) -> dict[str, str]:
    return {key: label for key, label in dimensions_for(scenario)}


def rubric_prompt_block(scenario: str) -> str:
    lines = ["评分必须先写扣分理由再给 0-100 整数。锚点："]
    for key, label in dimensions_for(scenario):
        anchors = RUBRIC.get(key) or {}
        bits = "；".join(f"{score}分={desc}" for score, desc in anchors.items())
        lines.append(f"- {label}({key}): {bits}")
    lines.append("禁止把所有维度都打到 78-85；有缺陷必须拉开分差。")
    return "\n".join(lines)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def fuse_scores(
    semantic: float | None,
    prosody: float | None,
    visual: float | None,
) -> tuple[float, list[str]]:
    """按 70/15/15 融合；缺模态时对剩余权重归一化，而不是给 0 分。"""
    parts: list[tuple[str, float, float]] = []
    degraded: list[str] = []
    if semantic is None:
        degraded.append("semantic")
    else:
        parts.append(("semantic", _clamp(semantic), SEMANTIC_WEIGHT))
    if prosody is None:
        degraded.append("prosody")
    else:
        parts.append(("prosody", _clamp(prosody), PROSODY_WEIGHT))
    if visual is None:
        degraded.append("visual")
    else:
        parts.append(("visual", _clamp(visual), VISUAL_WEIGHT))

    if not parts:
        return 0.0, degraded
    total_w = sum(w for _, _, w in parts)
    fused = sum(score * (w / total_w) for _, score, w in parts)
    return round(_clamp(fused), 1), degraded


_FILLER_RE = re.compile("|".join(FILLER_PATTERNS), re.IGNORECASE)


def _count_fillers(transcript: str) -> int:
    return len(_FILLER_RE.findall(transcript or ""))


def analyze_prosody(
    *,
    transcript: str,
    duration_sec: float,
    silence_sec: float = 0.0,
) -> dict[str, Any]:
    """由转写、时长与静音估算语速/停顿/填充词/流利度，无新依赖。"""
    text = (transcript or "").strip()
    char_count = len(re.sub(r"\s+", "", text))
    duration = max(0.0, float(duration_sec or 0.0))
    silence = max(0.0, min(float(silence_sec or 0.0), duration))
    speech_rate = (char_count / duration) if duration > 0 else 0.0
    pause_ratio = (silence / duration) if duration > 0 else 1.0
    filler_count = _count_fillers(text)
    reasons: list[str] = []

    # 中文面试约 3.5–5.5 字/秒为自然语速
    if duration < 4 and char_count < 20:
        rate_score = 35
        reasons.append("回答过短，信息量不足")
    elif speech_rate < 1.6:
        rate_score = 55
        reasons.append("语速偏慢或停顿过长")
    elif speech_rate > 8.0:
        rate_score = 60
        reasons.append("语速过快，听感急促")
    elif 3.0 <= speech_rate <= 6.0:
        rate_score = 90
    else:
        rate_score = 75

    if pause_ratio > 0.45:
        pause_score = 45
        reasons.append("静音占比过高")
    elif pause_ratio > 0.28:
        pause_score = 65
        reasons.append("停顿偏多")
    else:
        pause_score = 88

    filler_density = filler_count / max(char_count, 1)
    if filler_count >= 8 or filler_density > 0.08:
        filler_score = 45
        reasons.append(f"填充词偏多（约 {filler_count} 处）")
    elif filler_count >= 4:
        filler_score = 68
        reasons.append("有一定口头禅")
    else:
        filler_score = 90

    score = round(rate_score * 0.45 + pause_score * 0.25 + filler_score * 0.30, 1)
    return {
        "score": _clamp(score),
        "speech_rate": round(speech_rate, 2),
        "filler_count": filler_count,
        "pause_ratio": round(pause_ratio, 3),
        "duration_sec": round(duration, 2),
        "char_count": char_count,
        "reasons": reasons,
    }


def pcm_duration_sec(pcm_bytes: bytes, sample_rate: int = 16000, sample_width: int = 2) -> float:
    if not pcm_bytes:
        return 0.0
    return len(pcm_bytes) / float(sample_rate * sample_width)


def estimate_silence_sec(pcm_bytes: bytes, sample_rate: int = 16000, threshold: int = 400) -> float:
    """按 16-bit PCM 振幅粗估静音时长（无 numpy）。"""
    if not pcm_bytes or len(pcm_bytes) < 4:
        return 0.0
    frame = sample_rate // 10  # 100ms
    width = 2
    silent_frames = 0
    total_frames = 0
    for i in range(0, len(pcm_bytes) - width * frame, width * frame):
        total_frames += 1
        peak = 0
        chunk = pcm_bytes[i : i + width * frame]
        for j in range(0, len(chunk) - 1, 2):
            sample = int.from_bytes(chunk[j : j + 2], "little", signed=True)
            mag = abs(sample)
            if mag > peak:
                peak = mag
        if peak < threshold:
            silent_frames += 1
    if total_frames == 0:
        return 0.0
    return silent_frames * 0.1


def vision_enabled() -> bool:
    try:
        from app.services.runtime_config import get_str

        flag = (get_str("interview_vision_enabled", "1") or "1").strip().lower()
        if flag in {"0", "false", "off", "no"}:
            return False
    except Exception:
        pass
    from app.services.ark_vision import ark_vision_available

    return ark_vision_available()


async def analyze_frames(frames: list[str], *, user_id: str = "") -> dict[str, Any] | None:
    """多帧一次 ark_vision_chat；失败返回 None 以便融合层降级。"""
    if not frames or not vision_enabled():
        return None
    from app.services.ark_vision import ark_vision_chat
    from app.services.llm import extract_json

    parts: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                "你是模拟面试仪态评审。根据考生关键帧评估眼神接触、坐姿稳定、表情是否放松。"
                "不要评价外貌。严格返回 JSON："
                '{"score":75,"eye_contact":70,"posture":80,"expression":70,"reasons":["..."]}'
            ),
        }
    ]
    for url in frames[:4]:
        src = url if str(url).startswith("data:") else url
        parts.append({"type": "image_url", "image_url": {"url": src}})
    try:
        raw = await asyncio.wait_for(
            ark_vision_chat(
                [{"role": "user", "content": parts}],
                temperature=0.2,
                timeout=18.0,
                user_id=user_id,
                endpoint="interview_vision",
            ),
            timeout=18.0,
        )
    except (asyncio.TimeoutError, Exception):
        return None
    data = extract_json(raw or "") or {}
    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        return None
    return {
        "score": _clamp(score),
        "eye_contact": data.get("eye_contact"),
        "posture": data.get("posture"),
        "expression": data.get("expression"),
        "reasons": list(data.get("reasons") or []),
    }

