"""校招官网导航 + 参考日历（静态，不爬网页）。"""
from __future__ import annotations

from typing import Any

PORTALS: list[dict[str, Any]] = [
    {
        "id": "bytedance",
        "name": "字节跳动",
        "group": "互联网",
        "url": "https://jobs.bytedance.com/campus",
        "intern_url": "https://jobs.bytedance.com/campus",
        "note": "校招/实习同一入口，勾选「正式」或「实习」。",
    },
    {
        "id": "tencent",
        "name": "腾讯",
        "group": "互联网",
        "url": "https://join.qq.com",
        "intern_url": "https://join.qq.com",
        "note": "青云计划等校招以官网为唯一投递入口。",
    },
    {
        "id": "alibaba",
        "name": "阿里巴巴",
        "group": "互联网",
        "url": "https://talent.alibaba.com",
        "intern_url": "https://talent.alibaba.com",
        "note": "进入后选择应届生/实习项目再投递。",
    },
    {
        "id": "meituan",
        "name": "美团",
        "group": "互联网",
        "url": "https://zhaopin.meituan.com/web/campus",
        "intern_url": "https://zhaopin.meituan.com/web/campus",
        "note": "含应届校招、转正实习与日常实习。",
    },
    {
        "id": "jd",
        "name": "京东",
        "group": "互联网",
        "url": "https://campus.jd.com",
        "intern_url": "https://campus.jd.com",
        "note": "技术/产品/采销/物流等方向。",
    },
    {
        "id": "baidu",
        "name": "百度",
        "group": "互联网",
        "url": "https://talent.baidu.com/jobs/campus",
        "intern_url": "https://talent.baidu.com/jobs/campus",
        "note": "校招与实习岗位在人才官网切换。",
    },
    {
        "id": "netease",
        "name": "网易",
        "group": "互联网",
        "url": "https://campus.163.com",
        "intern_url": "https://campus.163.com",
        "note": "互娱/云音乐/有道等 BU 分入口，以官网为准。",
    },
    {
        "id": "xiaomi",
        "name": "小米",
        "group": "互联网",
        "url": "https://hr.xiaomi.com",
        "intern_url": "https://hr.xiaomi.com",
        "note": "校园招聘入口在招聘首页切换。",
    },
    {
        "id": "kuaishou",
        "name": "快手",
        "group": "互联网",
        "url": "https://campus.kuaishou.com",
        "intern_url": "https://campus.kuaishou.com",
        "note": "校招官网。",
    },
    {
        "id": "didi",
        "name": "滴滴",
        "group": "互联网",
        "url": "https://campus.didiglobal.com",
        "intern_url": "https://campus.didiglobal.com",
        "note": "校招/实习请以官网当期项目为准。",
    },
    {
        "id": "pinduoduo",
        "name": "拼多多",
        "group": "互联网",
        "url": "https://careers.pinduoduo.com",
        "intern_url": "https://careers.pinduoduo.com",
        "note": "校招与社招在同一招聘站。",
    },
    {
        "id": "huawei",
        "name": "华为",
        "group": "硬件制造",
        "url": "https://career.huawei.com/reccampportal/portal5/index.html",
        "intern_url": "https://career.huawei.com/reccampportal/portal5/index.html",
        "note": "校园招聘门户，含「天才少年」等专项。",
    },
    {
        "id": "zte",
        "name": "中兴通讯",
        "group": "硬件制造",
        "url": "https://job.zte.com.cn/cn/campus-recruitment",
        "intern_url": "https://job.zte.com.cn/cn/campus-recruitment",
        "note": "校园招聘专栏。",
    },
    {
        "id": "dji",
        "name": "大疆",
        "group": "硬件制造",
        "url": "https://we.dji.com/zh-CN/campus",
        "intern_url": "https://we.dji.com/zh-CN/campus",
        "note": "校园招聘入口。",
    },
    {
        "id": "li",
        "name": "理想汽车",
        "group": "新能源车",
        "url": "https://www.lixiang.com/recruit",
        "intern_url": "https://www.lixiang.com/recruit",
        "note": "招聘页切换校招/实习。",
    },
    {
        "id": "xiaopeng",
        "name": "小鹏汽车",
        "group": "新能源车",
        "url": "https://xiaopeng.jobs.feishu.cn.com/school",
        "intern_url": "https://xiaopeng.jobs.feishu.cn.com/internship",
        "note": "飞书招聘校园通道。",
    },
    {
        "id": "gwy",
        "name": "国家公务员局",
        "group": "升学考公",
        "url": "http://www.scs.gov.cn",
        "intern_url": "",
        "note": "国考公告与报名以官网为准。",
    },
    {
        "id": "yz",
        "name": "中国研究生招生信息网",
        "group": "升学考公",
        "url": "https://yz.chsi.com.cn",
        "intern_url": "",
        "note": "考研报名、调剂与成绩查询。",
    },
]


_ACCENTS = {
    "bytedance": "#325ab4",
    "tencent": "#12b7f5",
    "alibaba": "#ff6a00",
    "meituan": "#ffc300",
    "jd": "#e1251b",
    "baidu": "#2932e1",
    "netease": "#c20c0c",
    "xiaomi": "#ff6900",
    "kuaishou": "#ff4906",
    "didi": "#ff7e33",
    "pinduoduo": "#e02e24",
    "huawei": "#cf0a2c",
    "zte": "#0b5cab",
    "dji": "#000000",
    "li": "#1a1a1a",
    "xiaopeng": "#f15a24",
    "gwy": "#c41e3a",
    "yz": "#1d4ed8",
}
_LOGO_HOSTS = {
    "bytedance": "bytedance.com",
    "tencent": "qq.com",
    "alibaba": "alibaba.com",
    "meituan": "meituan.com",
    "jd": "jd.com",
    "baidu": "baidu.com",
    "netease": "163.com",
    "xiaomi": "mi.com",
    "kuaishou": "kuaishou.com",
    "didi": "didiglobal.com",
    "pinduoduo": "pinduoduo.com",
    "huawei": "huawei.com",
    "zte": "zte.com.cn",
    "dji": "dji.com",
    "li": "lixiang.com",
    "xiaopeng": "xiaopeng.com",
    "gwy": "scs.gov.cn",
    "yz": "chsi.com.cn",
}
for _p in PORTALS:
    _p["accent"] = _ACCENTS.get(_p["id"], "#f59e0b")
    _p["logo_host"] = _LOGO_HOSTS.get(_p["id"], "")


WINDOWS: list[dict[str, Any]] = [
    {
        "id": "autumn-open",
        "title": "秋招网申高峰",
        "when": "8–10 月",
        "season": "autumn",
        "portal_ids": ["bytedance", "tencent", "alibaba", "meituan", "huawei"],
        "note": "头部互联网/硬件多在 8 月启动次年校招，以官网为准。",
    },
    {
        "id": "autumn-oa",
        "title": "秋招笔试/面试",
        "when": "9–12 月",
        "season": "autumn",
        "portal_ids": ["bytedance", "tencent", "alibaba", "jd", "baidu"],
        "note": "网申后进入在线测评与多轮面试，进度只看各司邮件/官网。",
    },
    {
        "id": "intern-daily",
        "title": "日常实习",
        "when": "全年",
        "season": "intern",
        "portal_ids": ["bytedance", "meituan", "huawei", "dji"],
        "note": "大二/大三可投日常实习，与校招批次独立。",
    },
    {
        "id": "spring",
        "title": "春招补录",
        "when": "2–4 月",
        "season": "spring",
        "portal_ids": ["jd", "netease", "xiaomi", "kuaishou"],
        "note": "秋招未招满岗位的补录窗口，岗位量通常少于秋招。",
    },
    {
        "id": "gwy-yz",
        "title": "国考 / 考研关键节点",
        "when": "10 月报名 · 12 月笔试",
        "season": "exam",
        "portal_ids": ["gwy", "yz"],
        "note": "具体日期每年由官网公告，本站只做入口导航。",
    },
]


def list_portals(group: str = "") -> list[dict[str, Any]]:
    key = (group or "").strip()
    if not key:
        return list(PORTALS)
    return [p for p in PORTALS if p["group"] == key]


def list_windows() -> list[dict[str, Any]]:
    by_id = {p["id"]: p for p in PORTALS}
    out: list[dict[str, Any]] = []
    for win in WINDOWS:
        companies = [by_id[i]["name"] for i in win["portal_ids"] if i in by_id]
        out.append({**win, "companies": companies})
    return out


def portal_brief(limit: int = 6, group: str = "互联网") -> list[dict[str, str]]:
    rows = list_portals(group)[:limit]
    return [{"id": r["id"], "name": r["name"], "url": r["url"]} for r in rows]
