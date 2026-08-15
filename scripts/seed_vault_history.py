"""为演示账号灌入「用了很久」的星轨知识库样本（幂等覆盖正文 + 回填时间戳）。

默认用户 student001。用法（项目根）:
  .\\.venv\\Scripts\\python.exe scripts\\seed_vault_history.py
  .\\.venv\\Scripts\\python.exe scripts\\seed_vault_history.py --user student001 --analyze
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal, init_db  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.vault import VaultFile  # noqa: E402
from app.services import vault_service as vault  # noqa: E402


def _utc(days_ago: float, hour: int = 14, minute: int = 30) -> datetime:
    base = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return base.replace(hour=hour % 24, minute=minute % 60, second=20, microsecond=0)


# (相对路径, 距今天数, 正文)
NOTES: list[tuple[str, float, str]] = [
    (
        "10-Planets/computer-network/osi-model.md",
        118,
        """---
title: OSI 七层模型
galaxy_slug: computer-network
planet_slug: osi-model
tags: [network, foundation, 考研]
---

# OSI 七层模型

从下到上：物理 → 数据链路 → 网络 → 传输 → 会话 → 表示 → 应用。

## 我的理解

- 考试常考「哪一层做拥塞控制」→ [[tcp-protocol|TCP]] 在传输层。
- 和 TCP/IP 四层对照：应用层合并了上三层。

## 易错

路由器工作在网络层；交换机主要在数据链路层。

相关剪藏：[[20260203-OSI分层口诀]]
""",
    ),
    (
        "10-Planets/computer-network/tcp-protocol.md",
        96,
        """---
title: TCP 协议精要
galaxy_slug: computer-network
planet_slug: tcp-protocol
tags: [network, tcp, 薄弱]
---

# TCP 协议精要

可靠传输：序号、确认、重传、流量控制、拥塞控制。

## 三次握手

SYN → SYN+ACK → ACK。为什么不是两次？防止已失效连接请求突然传到服务器。

## 和 UDP

见 [[osi-model]]。UDP 适合实时音视频；TCP 适合文件与 HTTP。

## 错题反思

上次把「慢启动阈值」搞混了 → 见 [[错题-TCP拥塞窗口]]。
""",
    ),
    (
        "10-Planets/computer-network/http-https.md",
        72,
        """---
title: HTTP / HTTPS
galaxy_slug: computer-network
planet_slug: http-https
tags: [network, web]
---

# HTTP / HTTPS

HTTPS = HTTP + TLS。证书、对称密钥协商。

前置：[[tcp-protocol]]、[[osi-model]]。

状态码：301/302、304、404、500 要能口述场景。
""",
    ),
    (
        "10-Planets/data-structure/binary-tree.md",
        105,
        """---
title: 二叉树遍历与性质
galaxy_slug: data-structure
planet_slug: binary-tree
tags: [ds, tree, 费曼]
---

# 二叉树

先序 / 中序 / 后序 / 层序。由先序+中序可唯一确定一棵树。

## 费曼讲解草稿

「二叉树就像家谱：每个节点最多两个孩子……」→ 模板见 [[费曼讲解]]。

关联：[[排序算法对比]]、日记 [[2026-03-12]]。
""",
    ),
    (
        "10-Planets/data-structure/sorting.md",
        88,
        """---
title: 排序算法对比
galaxy_slug: data-structure
planet_slug: sorting
tags: [ds, sort]
---

# 排序算法对比

| 算法 | 平均 | 最坏 | 稳定 |
|------|------|------|------|
| 快排 | nlogn | n² | 否 |
| 归并 | nlogn | nlogn | 是 |
| 堆排 | nlogn | nlogn | 否 |

快排分区写挂了三次，剪藏在 [[20260328-快排partition踩坑]]。
""",
    ),
    (
        "10-Planets/operating-system/process-thread.md",
        64,
        """---
title: 进程与线程
galaxy_slug: operating-system
planet_slug: process-thread
tags: [os, concurrency]
---

# 进程与线程

进程是资源分配单位，线程是调度单位。

死锁四个条件：互斥、占有且等待、不可抢占、循环等待。

对比网络：[[tcp-protocol]] 的「连接」不是 OS 进程，别混。
""",
    ),
    (
        "10-Planets/computer-organization/cache.md",
        45,
        """---
title: Cache 映射与写策略
galaxy_slug: computer-organization
planet_slug: cache
tags: [co, cache]
---

# Cache

直接映射 / 全相联 / 组相联。写回 vs 写直达。

王道题目里「冲突缺失」老错 → [[错题-Cache映射]]。
""",
    ),
    (
        "20-Clips/20260203-OSI分层口诀.md",
        110,
        """---
title: OSI 分层口诀
tags: [clip, network]
source: starlib
---

# 剪藏 · OSI 分层口诀

「物数网传会表应」——物理到应用。

来自星库划词，页码约 p.12。关联 [[osi-model]]。
""",
    ),
    (
        "20-Clips/20260328-快排partition踩坑.md",
        85,
        """---
title: 快排 partition 踩坑
tags: [clip, ds, code]
source: codelab
---

# 剪藏 · 快排 partition

哨兵相遇时交换基准，边界 `i<=j` 写错会死循环。

关联 [[排序算法对比]]。
""",
    ),
    (
        "20-Clips/20260510-TCP抓包笔记.md",
        50,
        """---
title: TCP 抓包笔记
tags: [clip, tcp]
source: tutor
---

# 伴学对话摘录

ACK 号 = 期望的下一个字节序号。窗口字段是接收窗口。

→ [[tcp-protocol]]
""",
    ),
    (
        "00-Inbox/周末要整理的网络笔记.md",
        12,
        """---
title: 周末要整理的网络笔记
tags: [inbox]
---

# 周末待整理

- [ ] 把 [[http-https]] 补一张时序图
- [ ] 把错题 [[错题-TCP拥塞窗口]] 链回行星笔记
- [ ] 看王道网络第 3 章
""",
    ),
    (
        "00-Inbox/杂记-刷题节奏.md",
        28,
        """---
title: 刷题节奏
tags: [inbox, habit]
---

# 刷题节奏

每天选择题 20 + 大题 1。薄弱：组成原理 Cache、计网拥塞控制。
""",
    ),
    (
        "30-Habits/分析-2026-04-01.md",
        90,
        """---
title: 学情摘要 2026-04-01
tags: [habit, ai]
---

# 学情摘要 2026-04-01

阶段：计网夯实期。习惯：晚间番茄钟 ×2。薄弱：TCP 拥塞、子网划分。
""",
    ),
    (
        "30-Habits/分析-2026-06-15.md",
        30,
        """---
title: 学情摘要 2026-06-15
tags: [habit, ai]
---

# 学情摘要 2026-06-15

开始交叉复习数据结构与计网。费曼输出增加，代码舱提交变勤。
""",
    ),
    (
        "30-Habits/分析-2026-07-20.md",
        8,
        """---
title: 学情摘要 2026-07-20
tags: [habit, ai]
---

# 学情摘要 2026-07-20

近期高频：[[binary-tree]]、[[tcp-protocol]]。建议继续错题分镜讲解。
""",
    ),
    (
        "50-Daily/2026-03-12.md",
        100,
        """---
title: 日记 2026-03-12
tags: [daily]
---

# 2026-03-12

学了二叉树层序遍历，演武舱走了一遍 BFS。明天补 [[排序算法对比]]。
""",
    ),
    (
        "50-Daily/2026-04-18.md",
        75,
        """---
title: 日记 2026-04-18
tags: [daily]
---

# 2026-04-18

计网刷王道，卡在滑动窗口。写了 [[tcp-protocol]] 补充段。番茄钟 50min ×2。
""",
    ),
    (
        "50-Daily/2026-05-22.md",
        40,
        """---
title: 日记 2026-05-22
tags: [daily]
---

# 2026-05-22

操作系统进程同步题，PV 操作又晕。关联 [[process-thread]]。
""",
    ),
    (
        "50-Daily/2026-06-30.md",
        22,
        """---
title: 日记 2026-06-30
tags: [daily]
---

# 2026-06-30

月度复盘：网络 > 数据结构 > 组成。HTTPS 还没点亮，先锁 [[http-https]] 前置。
""",
    ),
    (
        "50-Daily/2026-07-28.md",
        2,
        """---
title: 日记 2026-07-28
tags: [daily]
---

# 2026-07-28

打开星轨知识库重构后的工作台，把旧剪藏都链到行星笔记。准备明天默写 OSI。
""",
    ),
    (
        "10-Planets/computer-network/错题-TCP拥塞窗口.md",
        55,
        """---
title: 错题 · TCP 拥塞窗口
galaxy_slug: computer-network
planet_slug: tcp-protocol
tags: [mistake, tcp]
---

# 错题反思 · TCP 拥塞窗口

题目把 cwnd 和 rwnd 搞反了。发送窗口 = min(cwnd, rwnd)。

模板：[[错题反思]]。主笔记：[[tcp-protocol]]。
""",
    ),
    (
        "10-Planets/computer-organization/错题-Cache映射.md",
        38,
        """---
title: 错题 · Cache 映射
galaxy_slug: computer-organization
planet_slug: cache
tags: [mistake, cache]
---

# 错题反思 · Cache 映射

直接映射：行号 = (块号) mod (Cache 行数)。冲突缺失≠容量缺失。

→ [[cache]]
""",
    ),
]


async def _user(session, username: str) -> User:
    row = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if not row:
        raise RuntimeError(f"用户不存在: {username}")
    return row


async def seed(username: str, do_analyze: bool) -> int:
    await init_db()
    async with AsyncSessionLocal() as session:
        user = await _user(session, username)
        await vault.ensure_vault(session, user)
        print(f"user={user.username} id={user.id}")
        print(f"vault={vault.vault_root(user.id)}")

        written = 0
        for rel, days_ago, content in NOTES:
            await vault.write_file(session, user, rel, content)
            written += 1
            print(f"  write {rel}")

        canvas = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "file",
                    "file": "10-Planets/computer-network/osi-model.md",
                    "x": -200,
                    "y": -80,
                    "width": 280,
                    "height": 80,
                },
                {
                    "id": "n2",
                    "type": "file",
                    "file": "10-Planets/computer-network/tcp-protocol.md",
                    "x": 120,
                    "y": -40,
                    "width": 280,
                    "height": 80,
                },
                {
                    "id": "n3",
                    "type": "file",
                    "file": "10-Planets/data-structure/binary-tree.md",
                    "x": -40,
                    "y": 140,
                    "width": 280,
                    "height": 80,
                },
                {
                    "id": "n4",
                    "type": "text",
                    "text": "计网 ↔ 数据结构交叉复习",
                    "x": -60,
                    "y": 40,
                    "width": 220,
                    "height": 60,
                },
            ],
            "edges": [
                {"id": "e1", "fromNode": "n1", "toNode": "n2", "label": "传输层"},
                {"id": "e2", "fromNode": "n2", "toNode": "n3", "label": "对比学习"},
            ],
        }
        await vault.write_canvas(session, user, "60-Canvas/默认画布.canvas", canvas)
        print("  write canvas")

        vrow = await vault.ensure_vault(session, user)
        meta = dict(vrow.meta_json or {})
        meta["bookmarks"] = [
            {"path": "10-Planets/computer-network/tcp-protocol.md", "title": "TCP 协议精要"},
            {"path": "10-Planets/data-structure/binary-tree.md", "title": "二叉树遍历"},
            {"path": "50-Daily/2026-07-28.md", "title": "近期日记"},
            {"path": "10-Planets/computer-network/错题-TCP拥塞窗口.md", "title": "错题·拥塞窗口"},
        ]
        vrow.meta_json = meta
        await session.commit()
        print(f"  bookmarks={len(meta['bookmarks'])}")

        # 先建索引，再回填时间（reindex 会刷新 updated_at）
        await vault.reindex_all(session, user)
        for rel, days_ago, _content in NOTES:
            ts = _utc(days_ago)
            row = (
                await session.execute(
                    select(VaultFile).where(VaultFile.user_id == user.id, VaultFile.path == rel)
                )
            ).scalar_one_or_none()
            if row:
                row.created_at = ts
                row.updated_at = ts + timedelta(hours=2 + abs(hash(rel)) % 48)
            full = vault.resolve_user_path(user.id, rel)
            if full.exists():
                epoch = ts.timestamp()
                os.utime(full, (epoch, epoch))
            print(f"  stamp {rel}  (-{days_ago:.0f}d)")
        await session.commit()
        print(f"Done: notes={written} (+canvas/bookmarks)")

        if do_analyze:
            print("Running vault analyze → profile…")
            result = await vault.analyze_vault_for_profile(session, user)
            print(
                f"  analyze ok={result.get('ok')} refreshed={result.get('profile_refreshed')} "
                f"summary={result.get('summary')}"
            )
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--user", default="student001")
    p.add_argument("--analyze", action="store_true", help="灌数后调用 AI 刷新画像")
    args = p.parse_args()
    return asyncio.run(seed(args.user, args.analyze))


if __name__ == "__main__":
    raise SystemExit(main())
