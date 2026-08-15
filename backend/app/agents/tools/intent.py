"""伴学意图识别（规则优先，可测、可离线）。"""
from __future__ import annotations

from typing import Literal

CompanionIntent = Literal[
    "chat", "path", "resource", "deck", "quiz", "feynman", "companion", "closed_loop", "sprint"
]


def classify_companion_intent(message: str, *, mode_hint: str = "") -> CompanionIntent:
    text = (message or "").strip().lower()
    hint = (mode_hint or "").strip().lower()
    if hint == "feynman":
        return "feynman"
    if hint == "companion":
        return "companion"
    if hint in ("closed_loop", "loop"):
        return "closed_loop"

    if any(k in text for k in ("费曼", "我来讲", "我讲一遍", "用自己的话")):
        return "feynman"
    if any(
        k in text
        for k in (
            "自动补强",
            "闭环",
            "根据弱项",
            "按评估生成",
            "一键补资源",
            "自动生成资源",
            "closed loop",
        )
    ):
        return "closed_loop"
    if any(k in text for k in ("冲刺", "备考计划", "考前", "倒计时", "快考试了", "要考试")):
        return "sprint"
    if any(k in text for k in ("学习路径", "学习计划", "下一步学", "路径规划", "怎么安排")):
        return "path"
    if any(k in text for k in ("闪卡", "卡片", "课件", "ppt", "deck")):
        return "deck"
    if any(k in text for k in ("出题", "练习题", "测验", "刷题", "quiz")):
        return "quiz"
    if any(k in text for k in ("讲义", "文档", "导图", "生成资料", "学习资源", "动画", "视频")):
        return "resource"
    if any(k in text for k in ("好累", "焦虑", "崩溃", "不想学", "压力大", "陪陪我")):
        return "companion"
    return "chat"
