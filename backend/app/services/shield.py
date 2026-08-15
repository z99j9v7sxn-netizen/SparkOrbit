"""思想防火墙 Agent：在所有 AI 输出到达前端前进行教育内容安全审核。"""
import logging
import re
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.services.llm import llm_available, llm_chat_raw

logger = logging.getLogger(__name__)

# 教育场景敏感词快筛（极速本地层）
_BLOCKED_PATTERNS = [
    r"自杀|自残|跳楼|割腕",
    r"色情|淫秽|裸聊",
    r"赌博|博彩|六合彩",
    r"毒品|吸毒|冰毒",
    r"暴力恐怖|制造炸弹",
    r"作弊神器|代考|枪手",
    r"翻墙|VPN.*违法",
]

_BLOCKED_RE = re.compile("|".join(_BLOCKED_PATTERNS), re.IGNORECASE)

# 管理端「补充敏感词」编译缓存：(原始串, 编译结果)
_extra_cache: tuple[str, Optional[re.Pattern]] = ("", None)

SAFE_REPLACEMENT = "该内容不符合教育价值观，已自动过滤。请聚焦学习成长与知识探索。"

SHIELD_SYSTEM = """你是 SparkOrbit 星轨学图的思想防火墙 Agent。
请审核以下 AI 输出是否符合教育价值观：积极、健康、鼓励学习、无暴力色情赌博等有害内容。
严格返回 JSON：{"safe": true/false, "reason": "若不安全简述原因"}。"""


def _extra_pattern() -> Optional[re.Pattern]:
    """管理端配置中心补充的敏感词（逗号/换行分隔），带编译缓存。"""
    global _extra_cache
    from app.services import runtime_config

    raw = runtime_config.get_str("shield_extra_words", "")
    if raw == _extra_cache[0]:
        return _extra_cache[1]
    words = [re.escape(w.strip()) for w in re.split(r"[,，\n]", raw) if w.strip()]
    pattern = re.compile("|".join(words), re.IGNORECASE) if words else None
    _extra_cache = (raw, pattern)
    return pattern


def _keyword_blocked(text: str) -> bool:
    if _BLOCKED_RE.search(text or ""):
        return True
    extra = _extra_pattern()
    return bool(extra and extra.search(text or ""))


async def review_output(text: str) -> Dict[str, Any]:
    """审核 AI 输出，返回 {safe, filtered, reason}。"""
    if not text or not text.strip():
        return {"safe": True, "filtered": text, "reason": ""}

    if _keyword_blocked(text):
        return {"safe": False, "filtered": SAFE_REPLACEMENT, "reason": "命中本地敏感词规则"}

    from app.services import runtime_config

    settings = get_settings()
    use_llm = runtime_config.get_bool("shield_use_llm", settings.shield_use_llm)
    if not use_llm or not llm_available():
        return {"safe": True, "filtered": text, "reason": ""}

    try:
        # 必须用 llm_chat_raw，禁止走 llm_chat 以免无限递归
        raw = await llm_chat_raw(
            [
                {"role": "system", "content": SHIELD_SYSTEM},
                {"role": "user", "content": f"待审核内容：\n{text[:2000]}"},
            ],
            temperature=0.0,
            response_json=True,
            timeout=20.0,
        )
        if raw:
            import json

            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end > start:
                data = json.loads(raw[start : end + 1])
                if data.get("safe") is False:
                    return {
                        "safe": False,
                        "filtered": SAFE_REPLACEMENT,
                        "reason": str(data.get("reason", "LLM 审核未通过")),
                    }
    except Exception as exc:  # noqa: BLE001
        logger.warning("shield LLM review failed: %s", exc)

    return {"safe": True, "filtered": text, "reason": ""}


async def filter_text(text: str) -> str:
    """便捷方法：返回过滤后的安全文本。"""
    result = await review_output(text)
    return str(result.get("filtered", text))


async def filter_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """过滤消息列表中 assistant 角色的内容。"""
    out: List[Dict[str, str]] = []
    for msg in messages:
        if msg.get("role") == "assistant":
            filtered = await filter_text(msg.get("content", ""))
            out.append({**msg, "content": filtered})
        else:
            out.append(msg)
    return out
