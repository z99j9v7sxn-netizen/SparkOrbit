"""企业面经：自编常见题，不爬第三方题库。"""
from __future__ import annotations

from typing import Any

QUESTIONS: list[dict[str, Any]] = [
    {
        "id": "bd-1",
        "company_id": "bytedance",
        "company": "字节跳动",
        "job_role": "backend",
        "kind": "tech",
        "question": "请设计一个短视频点赞服务：如何保证高并发下计数准确，又避免把所有请求打到单库？",
    },
    {
        "id": "bd-2",
        "company_id": "bytedance",
        "company": "字节跳动",
        "job_role": "backend",
        "kind": "project",
        "question": "讲一个你负责过的后端项目：流量上来之后你先观察什么指标，怎么判断是代码问题还是容量问题？",
    },
    {
        "id": "bd-3",
        "company_id": "bytedance",
        "company": "字节跳动",
        "job_role": "frontend",
        "kind": "tech",
        "question": "长列表信息流如何做虚拟滚动？首屏和回顶时你会怎么处理占位高度？",
    },
    {
        "id": "bd-4",
        "company_id": "bytedance",
        "company": "字节跳动",
        "job_role": "algorithm",
        "kind": "tech",
        "question": "推荐场景里，你如何解释一次在线模型更新没有带来业务指标提升？会从哪些环节排查？",
    },
    {
        "id": "tx-1",
        "company_id": "tencent",
        "company": "腾讯",
        "job_role": "backend",
        "kind": "tech",
        "question": "即时通讯已读回执怎么设计？弱网、多端登录时如何保证状态最终一致？",
    },
    {
        "id": "tx-2",
        "company_id": "tencent",
        "company": "腾讯",
        "job_role": "product",
        "kind": "business",
        "question": "如果让你给微信「搜一搜」加一个校园场景入口，你怎么定义成功指标并做最小实验？",
    },
    {
        "id": "tx-3",
        "company_id": "tencent",
        "company": "腾讯",
        "job_role": "frontend",
        "kind": "project",
        "question": "讲一次你处理过的前端性能问题：如何定位是包体积、渲染还是接口等待？",
    },
    {
        "id": "ali-1",
        "company_id": "alibaba",
        "company": "阿里巴巴",
        "job_role": "backend",
        "kind": "business",
        "question": "大促库存超卖你怎么防？扣减发生在下单、支付还是履约，为什么？",
    },
    {
        "id": "ali-2",
        "company_id": "alibaba",
        "company": "阿里巴巴",
        "job_role": "algorithm",
        "kind": "tech",
        "question": "搜索排序里相关性与商业化如何权衡？你如何向业务解释一次 CTR 上升但 GMV 下降？",
    },
    {
        "id": "ali-3",
        "company_id": "alibaba",
        "company": "阿里巴巴",
        "job_role": "product",
        "kind": "soft",
        "question": "描述一次你和研发对需求范围谈不拢的经历：你做了什么，最终怎么收口？",
    },
    {
        "id": "hw-1",
        "company_id": "huawei",
        "company": "华为",
        "job_role": "backend",
        "kind": "tech",
        "question": "解释一次你做过的并发控制：锁、无锁、还是队列？各自的失败模式是什么？",
    },
    {
        "id": "hw-2",
        "company_id": "huawei",
        "company": "华为",
        "job_role": "algorithm",
        "kind": "tech",
        "question": "给你一段会偶发超时的服务调用，你如何系统化地做根因分析而不是只加超时重试？",
    },
    {
        "id": "mt-1",
        "company_id": "meituan",
        "company": "美团",
        "job_role": "backend",
        "kind": "project",
        "question": "外卖高峰期某个接口 P99 突然变差，你会按什么顺序看监控、日志和容量？",
    },
    {
        "id": "mt-2",
        "company_id": "meituan",
        "company": "美团",
        "job_role": "product",
        "kind": "business",
        "question": "如果骑手准时率下降，你如何拆问题：是调度、路况、商家出餐还是用户预期？",
    },
    {
        "id": "jd-1",
        "company_id": "jd",
        "company": "京东",
        "job_role": "backend",
        "kind": "tech",
        "question": "仓储系统里「可售库存」和「实物库存」为什么要分开？一次盘点差异你怎么对账？",
    },
    {
        "id": "baidu-1",
        "company_id": "baidu",
        "company": "百度",
        "job_role": "algorithm",
        "kind": "tech",
        "question": "大模型应用里，你如何评估一次 Prompt 改动是真提升还是评测集过拟合？",
    },
    {
        "id": "netease-1",
        "company_id": "netease",
        "company": "网易",
        "job_role": "frontend",
        "kind": "project",
        "question": "游戏或内容社区里，一次活动页在低端机卡顿，你怎么排优先级修复？",
    },
    {
        "id": "xiaomi-1",
        "company_id": "xiaomi",
        "company": "小米",
        "job_role": "backend",
        "kind": "tech",
        "question": "IoT 设备心跳上报量很大，你会如何做接入层限流和离线补偿？",
    },
    {
        "id": "dji-1",
        "company_id": "dji",
        "company": "大疆",
        "job_role": "algorithm",
        "kind": "tech",
        "question": "嵌入式视觉任务内存很紧，你会如何在精度和时延之间做取舍并验证？",
    },
    {
        "id": "li-1",
        "company_id": "li",
        "company": "理想汽车",
        "job_role": "backend",
        "kind": "business",
        "question": "车云协同里，车辆离线期间产生的数据如何保证上云后不丢、不乱序？",
    },
    {
        "id": "acad-1",
        "company_id": "academic",
        "company": "升学综合",
        "job_role": "cs-grad",
        "kind": "research",
        "question": "用两分钟讲清你的研究问题：现有方法差在哪，你的贡献边界是什么？",
    },
    {
        "id": "acad-2",
        "company_id": "academic",
        "company": "升学综合",
        "job_role": "cs-grad",
        "kind": "method",
        "question": "如果审稿人说实验不充分，你下一步会补哪些对照，而不是只加更多数据集？",
    },
    {
        "id": "acad-3",
        "company_id": "academic",
        "company": "升学综合",
        "job_role": "comprehensive",
        "kind": "comprehensive",
        "question": "为什么读这个方向而不是直接工作？未来三年你希望训练哪些研究能力？",
    },
    {
        "id": "gwy-1",
        "company_id": "gwy",
        "company": "选调/公考面试",
        "job_role": "comprehensive",
        "kind": "soft",
        "question": "基层调研发现数据和群众感受不一致，你会如何核实并向上汇报？",
    },
]


def list_career_questions(company: str = "", job_role: str = "") -> list[dict[str, Any]]:
    rows = QUESTIONS
    cid = (company or "").strip()
    role = (job_role or "").strip()
    if cid:
        rows = [q for q in rows if q["company_id"] == cid or q["company"] == cid]
    if role:
        rows = [q for q in rows if q["job_role"] == role]
    return list(rows)


def list_question_companies() -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    for q in QUESTIONS:
        seen.setdefault(q["company_id"], q["company"])
    return [{"id": k, "name": v} for k, v in seen.items()]
