"""星系 / 行星初始数据与演示学生 seed。"""
import asyncio
import math
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.galaxy import Galaxy, Planet
from app.models.mastery import PlanetMastery
from app.models.user import User
from app.services.rag import ingest_syllabus

# 每个星系：基础信息 + 行星列表（拓扑用 prerequisites 表达前置关系）
GALAXY_SEED = [
    {
        "slug": "computer-network",
        "name": "计算机网络星系",
        "description": "覆盖 OSI/TCP-IP、传输层协议、应用层协议与网络安全。",
        "color": "#2779a7",
        "orbit_radius": 11.0,
        "planets": [
            {"slug": "osi-model", "name": "OSI 七层模型", "difficulty": "easy", "orbit": 1, "pre": [], "tags": ["OSI", "分层"]},
            {"slug": "ip-basics", "name": "IP 地址与子网", "difficulty": "easy", "orbit": 1, "pre": [], "tags": ["IP", "子网掩码"]},
            {"slug": "tcp-protocol", "name": "TCP 协议", "difficulty": "medium", "orbit": 2, "pre": ["ip-basics"], "tags": ["TCP", "三次握手"]},
            {"slug": "udp-protocol", "name": "UDP 协议", "difficulty": "medium", "orbit": 2, "pre": ["ip-basics"], "tags": ["UDP", "无连接"]},
            {"slug": "http-https", "name": "HTTP / HTTPS", "difficulty": "medium", "orbit": 2, "pre": ["tcp-protocol"], "tags": ["HTTP", "TLS"]},
            {"slug": "dns", "name": "DNS 解析", "difficulty": "medium", "orbit": 3, "pre": ["http-https"], "tags": ["DNS", "递归查询"]},
            {"slug": "routing", "name": "路由与路由表", "difficulty": "hard", "orbit": 3, "pre": ["ip-basics"], "tags": ["路由", "最长前缀匹配"]},
            {"slug": "nat-firewall", "name": "NAT 与防火墙", "difficulty": "hard", "orbit": 3, "pre": ["routing"], "tags": ["NAT", "防火墙"]},
            {"slug": "socket", "name": "Socket 编程", "difficulty": "hard", "orbit": 4, "pre": ["tcp-protocol"], "tags": ["Socket", "套接字"]},
            {"slug": "network-security", "name": "网络安全基础", "difficulty": "hard", "orbit": 4, "pre": ["http-https", "nat-firewall"], "tags": ["安全", "加密"]},
        ],
    },
    {
        "slug": "data-structure",
        "name": "数据结构与算法星系",
        "description": "从线性表到图与经典算法，构建计算思维的核心骨架。",
        "color": "#7c5cff",
        "orbit_radius": 16.0,
        "planets": [
            {"slug": "array-linkedlist", "name": "数组与链表", "difficulty": "easy", "orbit": 1, "pre": [], "tags": ["数组", "链表"]},
            {"slug": "stack-queue", "name": "栈与队列", "difficulty": "easy", "orbit": 1, "pre": ["array-linkedlist"], "tags": ["栈", "队列"]},
            {"slug": "hash-table", "name": "哈希表", "difficulty": "medium", "orbit": 2, "pre": ["array-linkedlist"], "tags": ["哈希", "冲突"]},
            {"slug": "binary-tree", "name": "二叉树", "difficulty": "medium", "orbit": 2, "pre": ["stack-queue"], "tags": ["树", "遍历"]},
            {"slug": "bst", "name": "二叉搜索树", "difficulty": "medium", "orbit": 3, "pre": ["binary-tree"], "tags": ["BST", "查找"]},
            {"slug": "heap", "name": "堆与优先队列", "difficulty": "medium", "orbit": 3, "pre": ["binary-tree"], "tags": ["堆", "优先队列"]},
            {"slug": "graph", "name": "图与遍历", "difficulty": "hard", "orbit": 3, "pre": ["stack-queue"], "tags": ["图", "BFS", "DFS"]},
            {"slug": "sorting", "name": "排序算法", "difficulty": "medium", "orbit": 2, "pre": ["array-linkedlist"], "tags": ["排序", "复杂度"]},
            {"slug": "dp", "name": "动态规划", "difficulty": "hard", "orbit": 4, "pre": ["sorting"], "tags": ["DP", "状态转移"]},
            {"slug": "greedy", "name": "贪心算法", "difficulty": "hard", "orbit": 4, "pre": ["sorting"], "tags": ["贪心", "最优子结构"]},
        ],
    },
    {
        "slug": "operating-system",
        "name": "操作系统星系",
        "description": "进程、内存、文件与并发，理解程序背后的调度世界。",
        "color": "#f59e0b",
        "orbit_radius": 21.0,
        "planets": [
            {"slug": "process-thread", "name": "进程与线程", "difficulty": "easy", "orbit": 1, "pre": [], "tags": ["进程", "线程"]},
            {"slug": "cpu-scheduling", "name": "CPU 调度", "difficulty": "medium", "orbit": 2, "pre": ["process-thread"], "tags": ["调度", "时间片"]},
            {"slug": "sync-mutex", "name": "同步与互斥", "difficulty": "medium", "orbit": 2, "pre": ["process-thread"], "tags": ["互斥", "信号量"]},
            {"slug": "deadlock", "name": "死锁", "difficulty": "hard", "orbit": 3, "pre": ["sync-mutex"], "tags": ["死锁", "银行家算法"]},
            {"slug": "memory-mgmt", "name": "内存管理", "difficulty": "medium", "orbit": 2, "pre": ["process-thread"], "tags": ["分页", "分段"]},
            {"slug": "virtual-memory", "name": "虚拟内存", "difficulty": "hard", "orbit": 3, "pre": ["memory-mgmt"], "tags": ["虚拟内存", "缺页"]},
            {"slug": "page-replace", "name": "页面置换算法", "difficulty": "hard", "orbit": 4, "pre": ["virtual-memory"], "tags": ["LRU", "置换"]},
            {"slug": "file-system", "name": "文件系统", "difficulty": "medium", "orbit": 3, "pre": ["process-thread"], "tags": ["文件", "inode"]},
            {"slug": "io-mgmt", "name": "I/O 管理", "difficulty": "hard", "orbit": 4, "pre": ["file-system"], "tags": ["IO", "缓冲"]},
        ],
    },
    {
        "slug": "computer-organization",
        "name": "计算机组成原理星系",
        "description": "数制编码、CPU 与指令、存储层次、总线与 I/O，贯通硬件执行路径。",
        "color": "#06b6d4",
        "orbit_radius": 23.5,
        "planets": [
            {"slug": "number-system", "name": "数制与编码", "difficulty": "easy", "orbit": 1, "pre": [], "tags": ["数制", "补码"]},
            {"slug": "cpu-datapath", "name": "CPU 与数据通路", "difficulty": "medium", "orbit": 2, "pre": ["number-system"], "tags": ["CPU", "数据通路"]},
            {"slug": "instruction-set", "name": "指令系统", "difficulty": "medium", "orbit": 2, "pre": ["cpu-datapath"], "tags": ["指令", "寻址"]},
            {"slug": "storage-hierarchy", "name": "存储层次", "difficulty": "medium", "orbit": 2, "pre": ["number-system"], "tags": ["存储", "层次"]},
            {"slug": "cache-memory", "name": "Cache 与主存", "difficulty": "hard", "orbit": 3, "pre": ["storage-hierarchy"], "tags": ["Cache", "主存"]},
            {"slug": "bus-system", "name": "总线结构", "difficulty": "medium", "orbit": 3, "pre": ["cpu-datapath"], "tags": ["总线", "仲裁"]},
            {"slug": "io-system", "name": "输入输出系统", "difficulty": "hard", "orbit": 3, "pre": ["bus-system"], "tags": ["IO", "中断"]},
            {"slug": "pipeline-cpu", "name": "流水线与性能", "difficulty": "hard", "orbit": 4, "pre": ["instruction-set", "cache-memory"], "tags": ["流水线", "性能"]},
        ],
    },
    {
        "slug": "database",
        "name": "数据库星系",
        "description": "关系模型、SQL、索引与事务，掌握数据的存取与一致性。",
        "color": "#10b981",
        "orbit_radius": 26.0,
        "planets": [
            {"slug": "relational-model", "name": "关系模型", "difficulty": "easy", "orbit": 1, "pre": [], "tags": ["关系", "主键"]},
            {"slug": "sql-basics", "name": "SQL 基础", "difficulty": "easy", "orbit": 1, "pre": ["relational-model"], "tags": ["SQL", "查询"]},
            {"slug": "join", "name": "多表连接", "difficulty": "medium", "orbit": 2, "pre": ["sql-basics"], "tags": ["JOIN", "连接"]},
            {"slug": "normalization", "name": "范式与规范化", "difficulty": "medium", "orbit": 2, "pre": ["relational-model"], "tags": ["范式", "3NF"]},
            {"slug": "index", "name": "索引与 B+ 树", "difficulty": "hard", "orbit": 3, "pre": ["sql-basics"], "tags": ["索引", "B+树"]},
            {"slug": "transaction", "name": "事务与 ACID", "difficulty": "medium", "orbit": 3, "pre": ["sql-basics"], "tags": ["事务", "ACID"]},
            {"slug": "isolation", "name": "隔离级别与锁", "difficulty": "hard", "orbit": 4, "pre": ["transaction"], "tags": ["隔离级别", "锁"]},
            {"slug": "db-optimize", "name": "查询优化", "difficulty": "hard", "orbit": 4, "pre": ["index", "join"], "tags": ["优化", "执行计划"]},
        ],
    },
    {
        "slug": "higher-math",
        "name": "高等数学星系",
        "description": "极限、微积分、级数与线性代数、概率的数学宇宙。",
        "color": "#ef4444",
        "orbit_radius": 31.0,
        "planets": [
            {"slug": "limit", "name": "极限与连续", "difficulty": "easy", "orbit": 1, "pre": [], "tags": ["极限", "连续"]},
            {"slug": "derivative", "name": "导数与微分", "difficulty": "medium", "orbit": 2, "pre": ["limit"], "tags": ["导数", "微分"]},
            {"slug": "integral", "name": "不定积分与定积分", "difficulty": "medium", "orbit": 2, "pre": ["derivative"], "tags": ["积分", "牛顿-莱布尼茨"]},
            {"slug": "series", "name": "级数", "difficulty": "hard", "orbit": 3, "pre": ["integral"], "tags": ["级数", "收敛"]},
            {"slug": "multivariable", "name": "多元函数微分", "difficulty": "hard", "orbit": 3, "pre": ["derivative"], "tags": ["偏导", "多元"]},
            {"slug": "ode", "name": "常微分方程", "difficulty": "hard", "orbit": 4, "pre": ["integral"], "tags": ["微分方程", "通解"]},
            {"slug": "matrix", "name": "矩阵与行列式", "difficulty": "medium", "orbit": 2, "pre": [], "tags": ["矩阵", "行列式"]},
            {"slug": "linear-system", "name": "线性方程组", "difficulty": "medium", "orbit": 3, "pre": ["matrix"], "tags": ["线性方程组", "秩"]},
            {"slug": "eigen", "name": "特征值与特征向量", "difficulty": "hard", "orbit": 4, "pre": ["linear-system"], "tags": ["特征值", "对角化"]},
            {"slug": "probability", "name": "概率与随机变量", "difficulty": "medium", "orbit": 2, "pre": [], "tags": ["概率", "分布"]},
        ],
    },
]

# 演示学生（用于排行榜、班级视图、好友对比）
DEMO_STUDENTS = [
    {"username": "student001", "display_name": "张三", "lit": 4},
    {"username": "student002", "display_name": "李四", "lit": 8},
    {"username": "student003", "display_name": "王五", "lit": 2},
    {"username": "student004", "display_name": "赵六", "lit": 11},
    {"username": "student005", "display_name": "钱七", "lit": 6},
]


def _add_planets_for_galaxy(session: AsyncSession, galaxy: Galaxy, g: dict) -> None:
    """按轨道层分组，均匀分布角度写入行星。"""
    orbit_groups: dict[int, list] = {}
    for p in g["planets"]:
        orbit_groups.setdefault(p["orbit"], []).append(p)

    order = 0
    for orbit_index, planets in orbit_groups.items():
        count = len(planets)
        for i, p in enumerate(planets):
            angle = (360.0 / max(count, 1)) * i + orbit_index * 20.0
            session.add(
                Planet(
                    galaxy_id=galaxy.id,
                    slug=p["slug"],
                    name=p["name"],
                    description=p.get("desc", f"{g['name']} · {p['name']} 知识点"),
                    difficulty=p["difficulty"],
                    orbit_index=orbit_index,
                    angle_deg=round(angle % 360, 2),
                    radius_offset=round(math.sin(i) * 0.6, 2),
                    prerequisites=p["pre"],
                    question_tags=p["tags"],
                    sort_order=order,
                )
            )
            order += 1


async def seed_content(session: AsyncSession) -> None:
    """插入星系/行星（按 slug 幂等补缺），并为演示学生铺设初始点亮进度。"""
    existing_slugs = {
        row[0]
        for row in (await session.execute(select(Galaxy.slug))).all()
    }
    added = False
    for g_order, g in enumerate(GALAXY_SEED):
        if g["slug"] in existing_slugs:
            continue
        galaxy = Galaxy(
            slug=g["slug"],
            name=g["name"],
            description=g["description"],
            color=g["color"],
            orbit_radius=g["orbit_radius"],
            sort_order=g_order,
        )
        session.add(galaxy)
        await session.flush()
        _add_planets_for_galaxy(session, galaxy, g)
        existing_slugs.add(g["slug"])
        added = True
    if added:
        await session.commit()

    # 灌入 RAG 教学大纲（幂等 upsert：星系汇总 + 逐行星细粒度）
    galaxies = (await session.execute(select(Galaxy))).scalars().all()
    for g in galaxies:
        planets = (
            await session.execute(select(Planet).where(Planet.galaxy_id == g.id))
        ).scalars().all()
        syllabus = f"{g.name}\n{g.description}\n" + "\n".join(
            f"- {p.name}: {p.description} (标签: {', '.join(p.question_tags or [])})" for p in planets
        )
        await asyncio.to_thread(ingest_syllabus, g.slug, syllabus, "seed")
        for p in planets:
            planet_text = (
                f"知识点ID: {p.slug}\n名称: {p.name}\n所属星系: {g.name}\n"
                f"说明: {p.description}\n标签: {', '.join(p.question_tags or [])}\n"
                f"难度: {p.difficulty}"
            )
            await asyncio.to_thread(
                ingest_syllabus,
                g.slug,
                planet_text,
                "planet_seed",
                planet_slug=p.slug,
            )

    await _seed_demo_students(session)


async def _seed_demo_students(session: AsyncSession) -> None:
    """为演示学生创建账号，并按 lit 数量点亮前若干颗行星（跨星系）。"""
    all_planets = (await session.execute(select(Planet).order_by(Planet.sort_order))).scalars().all()
    if not all_planets:
        return
    planet_ids = [p.id for p in all_planets]

    for stu in DEMO_STUDENTS:
        result = await session.execute(select(User).where(User.username == stu["username"]))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                username=stu["username"],
                password_hash=hash_password("123456"),
                role="student",
                display_name=stu["display_name"],
            )
            session.add(user)
            await session.flush()

        # 已有掌握记录则跳过，避免重复铺设
        existing_mastery = await session.execute(
            select(func.count()).select_from(PlanetMastery).where(PlanetMastery.user_id == user.id)
        )
        if (existing_mastery.scalar() or 0) > 0:
            continue

        lit_n = min(stu["lit"], len(planet_ids))
        user.points = 0
        for idx, pid in enumerate(planet_ids):
            lit = idx < lit_n
            session.add(
                PlanetMastery(
                    user_id=user.id,
                    planet_id=pid,
                    status="lit" if lit else "dim",
                    score=88 if lit else 0,
                    attempts=1 if lit else 0,
                    correct_count=1 if lit else 0,
                    lit_at=datetime.utcnow() - timedelta(days=idx) if lit else None,
                )
            )
        user.points = lit_n * 10
        if lit_n >= 8:
            user.mood = "celebrate"
            user.streak_days = 7
        elif lit_n <= 2:
            user.mood = "confused"
            user.streak_days = 1
    await session.commit()
