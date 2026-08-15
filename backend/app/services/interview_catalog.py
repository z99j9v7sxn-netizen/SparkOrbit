"""模拟面试岗位 / 升学场景模板与兜底题库。"""
from __future__ import annotations

from typing import Any

JOB_ROLES: list[dict[str, str]] = [
    {
        "key": "frontend",
        "label": "前端开发",
        "scenario": "job",
        "family": "tech",
        "description": "校招/实习前端：框架、工程化、项目经历",
    },
    {
        "key": "backend",
        "label": "后端开发",
        "scenario": "job",
        "family": "tech",
        "description": "校招/实习后端：服务设计、数据库、并发",
    },
    {
        "key": "algorithm",
        "label": "算法工程师",
        "scenario": "job",
        "family": "tech",
        "description": "算法岗：模型基础、项目落地、复杂度",
    },
    {
        "key": "product",
        "label": "产品经理",
        "scenario": "job",
        "family": "biz",
        "description": "产品岗：需求洞察、优先级、沟通协同",
    },
    {
        "key": "ops",
        "label": "运营",
        "scenario": "job",
        "family": "biz",
        "description": "运营岗：增长、内容、数据分析",
    },
    {
        "key": "cs-grad",
        "label": "计算机考研复试",
        "scenario": "academic",
        "family": "grad",
        "description": "计算机相关专业复试：专业课深挖 + 综合素质",
    },
    {
        "key": "ee-grad",
        "label": "电子信息考研复试",
        "scenario": "academic",
        "family": "grad",
        "description": "电子信息类复试：电路/信号基础 + 科研潜质",
    },
    {
        "key": "comprehensive",
        "label": "综合评价 / 自主招生",
        "scenario": "academic",
        "family": "admissions",
        "description": "综评面试：学科兴趣、批判思维、表达条理",
    },
]

QUESTION_KIND_LABELS_JOB = {
    "tech": "技术基础",
    "project": "项目经验",
    "business": "业务理解",
    "soft": "软技能",
}

QUESTION_KIND_LABELS_ACADEMIC = {
    "subject": "学科深挖",
    "method": "方法与推导",
    "research": "科研潜质",
    "comprehensive": "综合素质",
}

QUESTION_KINDS_JOB = ["tech", "project", "business", "soft"]
QUESTION_KINDS_ACADEMIC = ["subject", "method", "research", "comprehensive"]

_FALLBACK: dict[str, list[dict[str, str]]] = {
    "frontend": [
        {"kind": "tech", "question": "请用自己的话解释虚拟 DOM 解决了什么问题，以及它的主要代价。"},
        {"kind": "project", "question": "讲一个你负责过的前端项目：你做了什么、遇到什么性能或兼容问题、如何验证效果。"},
        {"kind": "business", "question": "如果产品要求一周内上线一个活动页，但设计稿天天改，你会怎么沟通和拆任务？"},
        {"kind": "soft", "question": "请做一分钟自我介绍，并说明你为什么适合前端岗位。"},
    ],
    "backend": [
        {"kind": "tech", "question": "数据库索引能解决什么问题？什么情况下加索引反而有害？"},
        {"kind": "project", "question": "描述一个你参与的后端接口或服务：流量、瓶颈、你做的优化和结果。"},
        {"kind": "business", "question": "用户投诉「下单成功但库存没扣」，你会按什么步骤排查？"},
        {"kind": "soft", "question": "请做一分钟自我介绍，并说明你最近一次主动推动的技术改进。"},
    ],
    "algorithm": [
        {"kind": "tech", "question": "过拟合和欠拟合分别怎么判断？各举一个你会采取的对策。"},
        {"kind": "project", "question": "讲一个你做过的模型或特征工程项目：数据、指标、你的贡献。"},
        {"kind": "business", "question": "线上指标突然下降，你会如何区分是数据问题、模型漂移还是业务变化？"},
        {"kind": "soft", "question": "请介绍自己，并说明你为什么想做算法而不是纯工程。"},
    ],
    "product": [
        {"kind": "tech", "question": "你如何判断一个需求该做还是不该做？请给出可复用的标准。"},
        {"kind": "project", "question": "讲一个你推动过的产品改动：背景、方案、上线后如何衡量。"},
        {"kind": "business", "question": "日活下降 10%，你会先看哪些数据、提出哪三个假设？"},
        {"kind": "soft", "question": "请做自我介绍，并说明你如何处理研发说「做不了」的情况。"},
    ],
    "ops": [
        {"kind": "tech", "question": "请解释一次你用数据验证过的运营动作，指标怎么选。"},
        {"kind": "project", "question": "讲一场你参与的活动或内容运营：目标、动作、复盘。"},
        {"kind": "business", "question": "拉新成本上升，你会怎么拆渠道并给出下一周动作。"},
        {"kind": "soft", "question": "请自我介绍，并说明你擅长协同哪些角色。"},
    ],
    "cs-grad": [
        {"kind": "subject", "question": "请解释进程和线程的区别，并说明什么时候必须用进程。"},
        {"kind": "method", "question": "哈希冲突有哪些解决方法？各有什么代价？"},
        {"kind": "research", "question": "如果让你跟一项课题，你准备怎么读文献并提出一个可验证的小问题？"},
        {"kind": "comprehensive", "question": "请做自我介绍，并说明你为什么报考这个方向。"},
    ],
    "ee-grad": [
        {"kind": "subject", "question": "请解释采样定理，并说明欠采样会发生什么。"},
        {"kind": "method", "question": "傅里叶变化在信号处理里解决什么问题？举一个你会用到的场景。"},
        {"kind": "research", "question": "你本科做过什么实验或课题？如果继续做，下一步想验证什么？"},
        {"kind": "comprehensive", "question": "请介绍自己，并说明你的优势与不足。"},
    ],
    "comprehensive": [
        {"kind": "subject", "question": "选一个你最感兴趣的学科问题，用三分钟讲清楚它为什么重要。"},
        {"kind": "method", "question": "当你的观点被老师否定时，你会怎么回应并继续把问题想清楚？"},
        {"kind": "research", "question": "请描述一次你主动探究未知问题的经历。"},
        {"kind": "comprehensive", "question": "请做自我介绍，并说明你希望大学四年成为什么样的人。"},
    ],
}


def list_job_roles(scenario: str = "") -> list[dict[str, str]]:
    if scenario in {"job", "academic"}:
        return [r for r in JOB_ROLES if r["scenario"] == scenario]
    return list(JOB_ROLES)


def get_role(key: str) -> dict[str, str] | None:
    for item in JOB_ROLES:
        if item["key"] == key:
            return item
    return None


def kinds_for(scenario: str) -> list[str]:
    return list(QUESTION_KINDS_ACADEMIC if scenario == "academic" else QUESTION_KINDS_JOB)


def kind_labels(scenario: str) -> dict[str, str]:
    return dict(QUESTION_KIND_LABELS_ACADEMIC if scenario == "academic" else QUESTION_KIND_LABELS_JOB)


def fallback_questions(job_role: str, count: int) -> list[dict[str, Any]]:
    bank = list(_FALLBACK.get(job_role) or _FALLBACK["backend"])
    out: list[dict[str, Any]] = []
    i = 0
    while len(out) < max(1, count):
        item = dict(bank[i % len(bank)])
        item["index"] = len(out)
        out.append(item)
        i += 1
    return out


def role_label(job_role: str) -> str:
    found = get_role(job_role)
    return found["label"] if found else job_role
