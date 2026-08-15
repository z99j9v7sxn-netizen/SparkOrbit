import json
import logging
import re
from typing import Any, Dict, List

from pydantic import ValidationError

from app.models.student_profile import PROFILE_DIMENSIONS
from app.schemas.student_profile import StudentProfileExtract
from app.services.llm import llm_available, llm_chat

logger = logging.getLogger(__name__)

PROFILE_JSON_SCHEMA: dict[str, Any] = StudentProfileExtract.model_json_schema()

SYSTEM_PROMPT = """
你是一个专业的教育心理学家与学习科学画像分析师。
请从给定的师生对话历史中，精确提取学生的 8 个认知维度：
1. major_background：专业背景
2. prior_knowledge：前置知识
3. cognitive_style：认知风格
4. mistake_tendency：易错倾向
5. learning_goal：学习目标
6. time_flexibility：时间弹性
7. modality_preference：资源模态偏好（视听视频 / 文本阅读 / 实操代码等）
8. motivation_level：学习动机强度（动力强弱与坚持度）

要求：
- 严格返回 JSON 对象，不要输出 Markdown，不要输出解释性前后缀。
- 每个维度包含 value、score、evidence。
- score 范围为 0-100，信息不足时 score 应较低。
- 如果信息不足以覆盖所有维度，请在 missing_dimensions 标记缺失维度，并在 follow_up_questions 给出追问问题。
- 只能基于对话证据推断，避免过度臆测。
""".strip()

DIMENSION_KEYS = list(PROFILE_DIMENSIONS)

FOLLOW_UP_BY_DIM: dict[str, str] = {
    "major_background": "你的专业或当前学习方向是什么？",
    "prior_knowledge": "你已经掌握了哪些相关前置知识？",
    "cognitive_style": "你更偏好图像化、推导式、案例式还是实践式学习？",
    "mistake_tendency": "你在学习中最常出现的错误类型是什么？",
    "learning_goal": "你本阶段最想达成的学习目标是什么？",
    "time_flexibility": "你每周可投入学习的时间是否稳定？",
    "modality_preference": "你更喜欢看视频动画、读文档，还是动手写代码练？",
    "motivation_level": "你最近学习动力怎么样，能否持续投入？",
}

_SKILL_TERMS = [
    "python",
    "java",
    "javascript",
    "typescript",
    "c\\+\\+",
    "c#",
    "golang",
    "go语言",
    "rust",
    "sql",
    "高等数学",
    "线性代数",
    "概率论",
    "数据结构",
    "算法",
    "机器学习",
    "深度学习",
    "pytorch",
    "tensorflow",
    "计算机网络",
    "操作系统",
    "数据库",
]

_MAJOR_PATTERNS = [
    (re.compile(r"(人工智能|AI)专业", re.I), "人工智能"),
    (re.compile(r"(计算机|软件工程|数据科学|电子信息|自动化|网络工程)专业"), None),
    (re.compile(r"我是(.{2,16}?)专业的?学生"), None),
    (re.compile(r"专业(?:是|为)?(.{2,16}?)(?:[，,。！!]|$)"), None),
]

_GOAL_PATTERNS = [
    re.compile(r"(?:最近想|想要?|打算|计划|目标是?)(?:学习|学|掌握|搞懂)?(.{2,24}?)(?:[，,。！!]|$)"),
    re.compile(r"学习目标[是为：:\s]*(.{2,24}?)(?:[，,。！!]|$)"),
]


def _clamp_score(raw: Any) -> int:
    try:
        score = int(round(float(raw)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def _coerce_dimension(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        text = raw.strip()
        return {"value": text, "score": 60 if text else 0, "evidence": []}
    if isinstance(raw, dict):
        value = str(raw.get("value") or raw.get("label") or raw.get("content") or "")
        evidence = raw.get("evidence") or []
        if isinstance(evidence, str):
            evidence = [evidence]
        elif not isinstance(evidence, list):
            evidence = []
        return {
            "value": value,
            "score": _clamp_score(raw.get("score", raw.get("confidence", 0))),
            "evidence": [str(item) for item in evidence if item],
        }
    return {"value": "", "score": 0, "evidence": []}


def _user_text(chat_history: List[Dict[str, str]]) -> str:
    parts = [
        str(message.get("content") or "")
        for message in chat_history
        if (message.get("role") or "") == "user"
    ]
    return "\n".join(parts).strip()


def _clean_snippet(text: str) -> str:
    return re.sub(r"\s+", "", text or "").strip(" ，,。.!！？?、:：")


_EMPTY_VALUES = {"", "未知", "待补充", "未明确", "不明"}

_MASTERY_VERBS = r"(?:精通|熟练|掌握|学会了?|学过|擅长|会|懂|了解)"


def _normalize_skill_label(raw: str) -> str:
    if re.fullmatch(r"python", raw, re.I):
        return "Python"
    if re.fullmatch(r"javascript", raw, re.I):
        return "JavaScript"
    if re.fullmatch(r"typescript", raw, re.I):
        return "TypeScript"
    if "c++" in raw.lower() or raw == "c\\+\\+":
        return "C++"
    if raw == "go语言":
        return "Go"
    return raw


def _asked_assistant_questions(chat_history: List[Dict[str, str]]) -> set[str]:
    asked: set[str] = set()
    for message in chat_history:
        if (message.get("role") or "") != "assistant":
            continue
        content = str(message.get("content") or "").strip()
        if content:
            asked.add(content)
    return asked


def _answers_after_question(chat_history: List[Dict[str, str]], question_substr: str) -> list[str]:
    """收集某类追问之后用户给出的答复。"""
    answers: list[str] = []
    pending = False
    for message in chat_history:
        role = message.get("role") or ""
        content = str(message.get("content") or "").strip()
        if role == "assistant" and question_substr in content:
            pending = True
            continue
        if pending and role == "user" and content:
            answers.append(content)
            pending = False
    return answers


def _heuristic_dims_from_chat(chat_history: List[Dict[str, str]]) -> dict[str, dict[str, Any]]:
    """从用户对话中规则抽取专业 / 前置知识 / 学习目标关键词。"""
    text = _user_text(chat_history)
    if not text:
        return {}

    dims: dict[str, dict[str, Any]] = {}
    lower = text.lower()

    major_value = ""
    major_evidence = ""
    for pattern, fixed in _MAJOR_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        major_value = fixed or _clean_snippet(match.group(1))
        major_evidence = match.group(0)
        break
    if not major_value and re.search(r"人工智能|计算机科学|软件工程", text):
        if "人工智能" in text or re.search(r"\bai\b", lower):
            major_value = "人工智能"
            major_evidence = "对话提及人工智能"
        elif "软件工程" in text:
            major_value = "软件工程"
            major_evidence = "对话提及软件工程"
        elif "计算机" in text:
            major_value = "计算机相关"
            major_evidence = "对话提及计算机"
    if major_value:
        dims["major_background"] = {
            "value": major_value,
            "score": 72,
            "evidence": [major_evidence or f"规则抽取：{major_value}"],
        }

    skills: list[str] = []
    mastery_skill = re.compile(
        _MASTERY_VERBS + r"\s*(" + "|".join(_SKILL_TERMS) + r")",
        re.I,
    )
    for match in mastery_skill.finditer(text):
        raw = match.group(1) or ""
        if raw:
            skills.append(_normalize_skill_label(raw))

    # 针对「前置知识」追问的答复：否定 / 技能短答（以后答为准）
    prior_q = FOLLOW_UP_BY_DIM["prior_knowledge"]
    prior_answers = _answers_after_question(chat_history, "前置知识")
    if not prior_answers and prior_q:
        prior_answers = _answers_after_question(chat_history, prior_q[:8])

    neg_re = re.compile(r"^(都?没有|没有掌握|暂无|不会|无|还没有|啥也没有|什么都不会).{0,8}$")
    last_neg = False
    answer_skills: list[str] = []
    for ans in prior_answers:
        cleaned = _clean_snippet(ans)
        if neg_re.match(cleaned) or cleaned in {"没有", "都没有", "无"}:
            last_neg = True
            answer_skills = []
            continue
        last_neg = False
        hit = False
        for term in _SKILL_TERMS:
            m = re.search(term, ans, re.I)
            if m:
                answer_skills.append(_normalize_skill_label(m.group(0)))
                hit = True
        if not hit and cleaned and 1 < len(cleaned) <= 20:
            answer_skills.append(cleaned)

    if answer_skills:
        skills.extend(answer_skills)
    elif last_neg:
        dims["prior_knowledge"] = {
            "value": "暂无相关前置知识",
            "score": 35,
            "evidence": ["用户对前置知识追问给出否定答复"],
        }

    if skills:
        prefix = "精通" if re.search(r"精通", text) else "已掌握"
        uniq = list(dict.fromkeys(skills))
        dims["prior_knowledge"] = {
            "value": f"{prefix}{'/'.join(uniq)}",
            "score": 78 if re.search(r"精通|熟练", text) else 68,
            "evidence": [f"规则抽取技能词：{', '.join(uniq)}"],
        }
    elif last_neg:
        dims["prior_knowledge"] = {
            "value": "暂无相关前置知识",
            "score": 35,
            "evidence": ["用户对前置知识追问给出否定答复"],
        }

    # 认知风格：动手实践 / 阅读 / 听讲
    style_answers = _answers_after_question(chat_history, "阅读") + _answers_after_question(
        chat_history, "动手实践"
    )
    style_text = " ".join(style_answers) or text
    if re.search(r"动手实践|实践|动手", style_text):
        dims["cognitive_style"] = {
            "value": "偏实践动手",
            "score": 75,
            "evidence": ["对话提及动手实践"],
        }
    elif re.search(r"阅读|看书", style_text):
        dims["cognitive_style"] = {
            "value": "偏阅读理解",
            "score": 70,
            "evidence": ["对话提及阅读"],
        }
    elif re.search(r"听讲|听课", style_text):
        dims["cognitive_style"] = {
            "value": "偏听讲输入",
            "score": 70,
            "evidence": ["对话提及听讲"],
        }

    # 易错：粗心等
    mistake_answers = _answers_after_question(chat_history, "错误类型")
    mistake_blob = " ".join(mistake_answers) or text
    if re.search(r"粗心|大意|马虎", mistake_blob):
        dims["mistake_tendency"] = {
            "value": "粗心大意导致失误",
            "score": 55,
            "evidence": ["用户自述易错：粗心大意"],
        }

    goal_value = ""
    goal_evidence = ""
    for pattern in _GOAL_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        goal_value = _clean_snippet(match.group(1))
        goal_evidence = match.group(0)
        if goal_value:
            break
    if goal_value:
        goal_value = re.sub(r"^(学习|学)", "", goal_value) or goal_value
        dims["learning_goal"] = {
            "value": f"学习{goal_value}" if not goal_value.startswith("学习") else goal_value,
            "score": 74,
            "evidence": [goal_evidence or f"规则抽取目标：{goal_value}"],
        }

    modality_blob = " ".join(_answers_after_question(chat_history, "视频")) + " " + text
    if re.search(r"视频|动画|看片|视听|讲解视频", modality_blob):
        dims["modality_preference"] = {
            "value": "偏视听视频",
            "score": 76,
            "evidence": ["对话提及视频/动画学习偏好"],
        }
    elif re.search(r"写代码|动手练|实操|实验|编程", modality_blob):
        dims["modality_preference"] = {
            "value": "偏实操代码",
            "score": 78,
            "evidence": ["对话提及实操/代码练习偏好"],
        }
    elif re.search(r"文档|阅读|看书|文字材料", modality_blob):
        dims["modality_preference"] = {
            "value": "偏文本阅读",
            "score": 72,
            "evidence": ["对话提及文档/阅读偏好"],
        }

    motive_blob = " ".join(_answers_after_question(chat_history, "动力")) + " " + text
    if re.search(r"动力很强|很有干劲|非常想学|拼命学|坚持每天", motive_blob):
        dims["motivation_level"] = {
            "value": "动机强，可持续投入",
            "score": 82,
            "evidence": ["对话体现较强学习动机"],
        }
    elif re.search(r"提不起劲|没动力|拖延|三天打鱼|不想学|倦怠", motive_blob):
        dims["motivation_level"] = {
            "value": "动机偏弱，需激励",
            "score": 38,
            "evidence": ["对话体现动机不足"],
        }
    elif re.search(r"动力一般|还行|看心情|有时想学", motive_blob):
        dims["motivation_level"] = {
            "value": "动机中等",
            "score": 58,
            "evidence": ["对话体现中等动机"],
        }

    return dims


def _is_empty_dim_value(value: str) -> bool:
    v = (value or "").strip()
    return v in _EMPTY_VALUES or v.startswith("未明确")


def _merge_heuristic(
    profile: StudentProfileExtract,
    chat_history: List[Dict[str, str]],
    *,
    fill_only_empty: bool = True,
) -> StudentProfileExtract:
    heuristics = _heuristic_dims_from_chat(chat_history)
    payload = profile.model_dump()

    for key, dim in heuristics.items():
        current_value = str((payload.get(key) or {}).get("value") or "").strip()
        if fill_only_empty and current_value and not _is_empty_dim_value(current_value):
            continue
        payload[key] = _coerce_dimension(dim)

    # 「未知/未明确」一律允许启发式覆盖
    for key, dim in heuristics.items():
        current_value = str((payload.get(key) or {}).get("value") or "").strip()
        if _is_empty_dim_value(current_value):
            payload[key] = _coerce_dimension(dim)

    missing = [
        key
        for key in DIMENSION_KEYS
        if _is_empty_dim_value(str((payload.get(key) or {}).get("value") or ""))
    ]
    payload["missing_dimensions"] = missing
    follow_ups = [FOLLOW_UP_BY_DIM[k] for k in missing if k in FOLLOW_UP_BY_DIM]
    existing = payload.get("follow_up_questions") or []
    if isinstance(existing, list):
        for q in existing:
            qs = str(q).strip()
            if qs and qs not in follow_ups:
                follow_ups.append(qs)

    asked = _asked_assistant_questions(chat_history)
    follow_ups = [q for q in follow_ups if q not in asked]
    payload["follow_up_questions"] = follow_ups[:6]

    parts = [
        str((payload[key] or {}).get("value") or "")
        for key in ("major_background", "prior_knowledge", "learning_goal")
        if not _is_empty_dim_value(str((payload.get(key) or {}).get("value") or ""))
    ]
    if parts:
        summary = "；".join(parts)
        old_summary = str(payload.get("summary") or "")
        if (not old_summary) or old_summary.startswith("画像抽取未完成") or "未知" in old_summary:
            payload["summary"] = summary

    return StudentProfileExtract.model_validate(_coerce_profile(payload))


def _fallback_profile(chat_history: List[Dict[str, str]], reason: str) -> StudentProfileExtract:
    text = "\n".join(message.get("content", "") for message in chat_history)
    profile = StudentProfileExtract(
        summary=f"画像抽取未完成：{reason}。已保留原始对话，等待进一步追问。对话摘录：{text[:300]}",
        missing_dimensions=list(PROFILE_DIMENSIONS),  # type: ignore[arg-type]
        follow_up_questions=list(FOLLOW_UP_BY_DIM.values()),
    )
    return _merge_heuristic(profile, chat_history, fill_only_empty=True)


def _coerce_profile(parsed: dict[str, Any]) -> dict[str, Any]:
    coerced = dict(parsed)
    for key in DIMENSION_KEYS:
        coerced[key] = _coerce_dimension(coerced.get(key))

    missing = coerced.get("missing_dimensions") or []
    if isinstance(missing, list):
        coerced["missing_dimensions"] = [m for m in missing if m in DIMENSION_KEYS]
    else:
        coerced["missing_dimensions"] = []

    follow_ups = coerced.get("follow_up_questions") or []
    if not isinstance(follow_ups, list):
        follow_ups = []
    coerced["follow_up_questions"] = [str(q) for q in follow_ups if q]

    if not coerced.get("summary"):
        parts = [coerced[key]["value"] for key in DIMENSION_KEYS if coerced[key]["value"]]
        coerced["summary"] = "；".join(parts[:3]) if parts else "画像已初步生成，部分维度信息尚不完整。"

    return coerced


def _extract_json_from_text(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return json.loads(text[start : end + 1])


async def extract_student_profile(chat_history: List[Dict[str, str]]) -> StudentProfileExtract:
    """调用 DeepSeek，将对话历史抽取为结构化学生画像；失败时用关键词规则兜底。"""

    if not llm_available():
        return _fallback_profile(chat_history, "未配置 DEEPSEEK_API_KEY")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *chat_history]
    try:
        content = await llm_chat(messages, temperature=0.3, response_json=True)
        if not content:
            raise RuntimeError("DeepSeek returned empty content")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = _extract_json_from_text(content)
        coerced = _coerce_profile(parsed if isinstance(parsed, dict) else {})
        profile = StudentProfileExtract.model_validate(coerced)
        return _merge_heuristic(profile, chat_history, fill_only_empty=True)
    except (KeyError, TypeError, json.JSONDecodeError, ValidationError, RuntimeError, Exception) as exc:
        logger.exception("DeepSeek profile extraction failed: %s", exc)
        return _fallback_profile(chat_history, f"大模型返回不可用：{exc.__class__.__name__}")
