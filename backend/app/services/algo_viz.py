"""演武舱：加载种子轨迹 / 按行星匹配 / AI 生成 / 可视化修改重跑。"""
from __future__ import annotations

import heapq
import json
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.galaxy import Planet
from app.models.user import User
from app.services import mastery_gates as gates
from app.services.spark import extract_json, spark_chat

_TRACE_DIR = Path(__file__).resolve().parents[1] / "data" / "viz_traces"
_CACHE: Optional[List[dict]] = None


def _load_all() -> list[dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    traces: list[dict] = []
    if _TRACE_DIR.is_dir():
        for p in sorted(_TRACE_DIR.glob("*.json")):
            try:
                traces.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
    _CACHE = traces
    return traces


def clear_trace_cache() -> None:
    """进程内热加载种子 JSON 时调用。"""
    global _CACHE
    _CACHE = None


def _validate_trace(data: dict) -> bool:
    """校验 AI 轨迹结构，不合格则回退种子/引擎。"""
    structure = (data.get("structure") or "array").lower()
    steps = data.get("steps") or []
    if not steps or not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            return False
        if structure == "array":
            if not isinstance(step.get("bars"), list):
                return False
        elif structure in ("tree", "graph"):
            if not isinstance(step.get("nodes"), list) or not isinstance(step.get("edges"), list):
                return False
        else:
            return False
    return True


def _edge_key(u: str, v: str) -> str:
    return f"{u}-{v}"


def _default_graph_nodes() -> list[dict]:
    return [
        {"id": "A", "label": "A", "x": 0.15, "y": 0.5},
        {"id": "B", "label": "B", "x": 0.45, "y": 0.25},
        {"id": "C", "label": "C", "x": 0.45, "y": 0.75},
        {"id": "D", "label": "D", "x": 0.75, "y": 0.15},
        {"id": "E", "label": "E", "x": 0.85, "y": 0.5},
    ]


def _default_dijkstra_nodes() -> list[dict]:
    return [
        {"id": "S", "label": "S", "x": 0.12, "y": 0.5},
        {"id": "B", "label": "B", "x": 0.38, "y": 0.75},
        {"id": "A", "label": "A", "x": 0.55, "y": 0.25},
        {"id": "T", "label": "T", "x": 0.88, "y": 0.5},
    ]


def _graph_bfs_trace(initial: dict[str, Any], title: str = "BFS 遍历（自定义）") -> dict[str, Any]:
    nodes: list[dict] = list(initial.get("nodes") or _default_graph_nodes())
    edges: list[list] = [list(e) for e in (initial.get("edges") or [["A", "B"], ["A", "C"], ["B", "D"], ["B", "E"], ["C", "E"]])]
    start = str(initial.get("start") or (nodes[0]["id"] if nodes else "A"))

    adj: dict[str, list[str]] = {}
    for e in edges:
        if len(e) < 2:
            continue
        u, v = str(e[0]), str(e[1])
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)

    steps: list[dict[str, Any]] = [
        {
            "line": 1,
            "narrate": f"图结构就绪，从起点 {start} 开始 BFS",
            "vars": {"start": start},
            "stack": ["bfs"],
            "nodes": nodes,
            "edges": edges,
            "highlight": [start],
        }
    ]
    visited: set[str] = set()
    q: deque[str] = deque([start])
    visited.add(start)

    while q:
        u = q.popleft()
        hl: list[str] = [u]
        nbrs: list[str] = []
        for v in adj.get(u, []):
            if v not in visited:
                visited.add(v)
                q.append(v)
                nbrs.append(v)
                hl.append(_edge_key(u, v))
        narrate = f"出队 {u}，访问 {u}"
        if nbrs:
            narrate += f"；将邻居 {', '.join(nbrs)} 入队"
        else:
            narrate += "；无未访问邻居"
        steps.append(
            {
                "line": 4,
                "narrate": narrate,
                "vars": {"current": u, "queue": str(list(q))},
                "stack": ["bfs"],
                "nodes": nodes,
                "edges": edges,
                "highlight": hl,
            }
        )

    order = [s["vars"].get("current") for s in steps[1:] if s["vars"].get("current")]
    steps.append(
        {
            "line": 6,
            "narrate": f"BFS 完成，访问序 {'→'.join(order)}",
            "vars": {"order": str(order)},
            "stack": ["bfs"],
            "nodes": nodes,
            "edges": edges,
            "highlight": list(visited),
        }
    )
    return {
        "id": f"custom-bfs-{uuid.uuid4().hex[:8]}",
        "title": title,
        "structure": "graph",
        "algo": "bfs",
        "code": "from collections import deque\n\ndef bfs(graph, start):\n    visited = set([start])\n    q = deque([start])\n    while q:\n        u = q.popleft()\n        for v in graph.get(u, []):\n            if v not in visited:\n                visited.add(v)\n                q.append(v)\n    return visited\n",
        "steps": steps,
        "planet_keywords": ["图", "BFS", "广度"],
        "initial": {"start": start, "nodes": nodes, "edges": edges},
    }


def _dijkstra_trace(initial: dict[str, Any], title: str = "Dijkstra 最短路（自定义）") -> dict[str, Any]:
    nodes: list[dict] = list(initial.get("nodes") or _default_dijkstra_nodes())
    edges: list[list] = [
        list(e)
        for e in (
            initial.get("edges")
            or [["S", "B", 2], ["S", "A", 4], ["B", "A", 1], ["B", "T", 5], ["A", "T", 3]]
        )
    ]
    start = str(initial.get("start") or (nodes[0]["id"] if nodes else "S"))
    target = str(initial.get("target") or (nodes[-1]["id"] if nodes else "T"))

    adj: dict[str, list[tuple[str, int]]] = {}
    for e in edges:
        if len(e) < 3:
            continue
        u, v, w = str(e[0]), str(e[1]), int(e[2])
        adj.setdefault(u, []).append((v, w))
        adj.setdefault(v, []).append((u, w))

    steps: list[dict[str, Any]] = [
        {
            "line": 1,
            "narrate": f"加权图就绪，从 {start} 到 {target} 求最短路",
            "vars": {"start": start, "target": target},
            "stack": ["dijkstra"],
            "nodes": nodes,
            "edges": edges,
            "highlight": [start],
        }
    ]
    dist: dict[str, float] = {start: 0}
    pq: list[tuple[float, str]] = [(0.0, start)]
    settled: set[str] = set()

    while pq:
        d, u = heapq.heappop(pq)
        if u in settled:
            continue
        settled.add(u)
        hl: list[str] = [u]
        relax_notes: list[str] = []
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
                hl.append(_edge_key(u, v))
                relax_notes.append(f"{u}→{v}={int(nd)}")
        narrate = f"弹出 {u}(dist={int(d)})"
        if relax_notes:
            narrate += f"；松弛 {', '.join(relax_notes)}"
        steps.append(
            {
                "line": 4,
                "narrate": narrate,
                "vars": {"current": u, "dist": str({k: int(v) for k, v in dist.items()})},
                "stack": ["dijkstra"],
                "nodes": nodes,
                "edges": edges,
                "highlight": hl,
            }
        )
        if u == target:
            break

    ans = int(dist.get(target, float("inf")))
    steps.append(
        {
            "line": 6,
            "narrate": f"到达 {target}，最短路权重 {ans}",
            "vars": {"answer": ans, "target": target},
            "stack": ["dijkstra"],
            "nodes": nodes,
            "edges": edges,
            "highlight": [target],
        }
    )
    return {
        "id": f"custom-dijkstra-{uuid.uuid4().hex[:8]}",
        "title": title,
        "structure": "graph",
        "algo": "dijkstra",
        "code": "import heapq\n\ndef dijkstra(graph, start, target):\n    dist = {start: 0}\n    pq = [(0, start)]\n    while pq:\n        d, u = heapq.heappop(pq)\n        if u == target:\n            return d\n        for v, w in graph.get(u, []):\n            nd = d + w\n            if nd < dist.get(v, float('inf')):\n                dist[v] = nd\n                heapq.heappush(pq, (nd, v))\n    return dist.get(target, float('inf'))\n",
        "steps": steps,
        "planet_keywords": ["最短路", "Dijkstra", "图"],
        "initial": {"start": start, "target": target, "nodes": nodes, "edges": edges},
    }


def _is_dijkstra_topic(algo: str, title: str, topic: str = "") -> bool:
    blob = f"{algo} {title} {topic}".lower()
    return "dijkstra" in blob or "最短路" in blob or "最短路径" in blob


def _is_dfs_topic(algo: str, title: str, topic: str = "") -> bool:
    blob = f"{algo} {title} {topic}".lower()
    if _is_dijkstra_topic(algo, title, topic):
        return False
    return "dfs" in blob or "深度优先" in blob or "深度搜索" in blob or ("深度" in blob and "广度" not in blob)


def _graph_dfs_trace(initial: dict[str, Any], title: str = "DFS 遍历（自定义）") -> dict[str, Any]:
    nodes: list[dict] = list(initial.get("nodes") or _default_graph_nodes())
    edges: list[list] = [list(e) for e in (initial.get("edges") or [["A", "B"], ["A", "C"], ["B", "D"], ["B", "E"], ["C", "E"]])]
    start = str(initial.get("start") or (nodes[0]["id"] if nodes else "A"))

    adj: dict[str, list[str]] = {}
    for e in edges:
        if len(e) < 2:
            continue
        u, v = str(e[0]), str(e[1])
        adj.setdefault(u, []).append(v)
        adj.setdefault(v, []).append(u)

    steps: list[dict[str, Any]] = [
        {
            "line": 1,
            "narrate": f"图结构就绪，从起点 {start} 开始 DFS（栈）",
            "vars": {"start": start},
            "stack": ["dfs"],
            "nodes": nodes,
            "edges": edges,
            "highlight": [start],
            "predict": {
                "question": "DFS 用栈时，从 A 出发先压入邻居 B、C（B 后入），下一步弹出的是？",
                "options": [
                    {"key": "A", "text": "B"},
                    {"key": "B", "text": "C"},
                    {"key": "C", "text": "D"},
                    {"key": "D", "text": "E"},
                ],
                "answer": "B",
            },
        }
    ]
    visited: set[str] = set()
    st: list[str] = [start]
    order: list[str] = []

    while st:
        u = st.pop()
        if u in visited:
            continue
        visited.add(u)
        order.append(u)
        hl: list[str] = [u]
        nbrs: list[str] = []
        # 逆序压栈，使邻接表顺序与 BFS 种子一致时先探索 B
        for v in reversed(adj.get(u, [])):
            if v not in visited:
                st.append(v)
                nbrs.append(v)
                hl.append(_edge_key(u, v))
        narrate = f"弹出 {u}，访问 {u}"
        if nbrs:
            narrate += f"；将未访问邻居 {', '.join(reversed(nbrs))} 压栈"
        else:
            narrate += "；无未访问邻居"
        step: dict[str, Any] = {
            "line": 4,
            "narrate": narrate,
            "vars": {"current": u, "stack": str(list(st)), "order": str(order)},
            "stack": ["dfs"],
            "nodes": nodes,
            "edges": edges,
            "highlight": hl,
        }
        if u == start and nbrs:
            step["predict"] = {
                "question": f"访问 {u} 后栈顶约为邻居之一，下一跳更可能深入哪条支路？",
                "options": [
                    {"key": "A", "text": "先深入先压入的邻居支路"},
                    {"key": "B", "text": "先深入后压入的邻居支路"},
                    {"key": "C", "text": "随机跳转"},
                    {"key": "D", "text": "立刻回起点"},
                ],
                "answer": "B",
            }
        steps.append(step)

    steps.append(
        {
            "line": 6,
            "narrate": f"DFS 完成，访问序 {'→'.join(order)}",
            "vars": {"order": str(order)},
            "stack": ["dfs"],
            "nodes": nodes,
            "edges": edges,
            "highlight": list(visited),
        }
    )
    return {
        "id": f"custom-dfs-{uuid.uuid4().hex[:8]}",
        "title": title,
        "structure": "graph",
        "algo": "dfs",
        "code": "def dfs(graph, start):\n    visited = set()\n    stack = [start]\n    order = []\n    while stack:\n        u = stack.pop()\n        if u in visited:\n            continue\n        visited.add(u)\n        order.append(u)\n        for v in reversed(graph.get(u, [])):\n            if v not in visited:\n                stack.append(v)\n    return order\n",
        "steps": steps,
        "planet_keywords": ["图", "DFS", "深度", "深度优先"],
        "initial": {"start": start, "nodes": nodes, "edges": edges, "algo": "dfs"},
    }


def _graph_engine_fallback(topic: str) -> dict[str, Any]:
    if _is_dijkstra_topic("", "", topic):
        t = _dijkstra_trace({}, f"{topic}（本地引擎）")
    elif _is_dfs_topic("", "", topic):
        t = _graph_dfs_trace({}, f"{topic}（本地引擎）")
    else:
        t = _graph_bfs_trace({}, f"{topic}（本地引擎）")
    return t


def list_traces() -> list[dict]:
    return [
        {
            "id": t.get("id"),
            "title": t.get("title"),
            "structure": t.get("structure"),
            "planet_keywords": t.get("planet_keywords") or [],
            "step_count": len(t.get("steps") or []),
        }
        for t in _load_all()
    ]


def get_trace(trace_id: str) -> dict | None:
    for t in _load_all():
        if t.get("id") == trace_id:
            return t
    return None


def match_trace_for_planet(planet_name: str, planet_desc: str = "") -> dict | None:
    blob = f"{planet_name} {planet_desc}".lower()
    best = None
    best_score = 0
    for t in _load_all():
        score = 0
        for kw in t.get("planet_keywords") or []:
            if str(kw).lower() in blob:
                score += 1
        if score > best_score:
            best_score = score
            best = t
    return best or (_load_all()[0] if _load_all() else None)


async def complete_viz(
    session: AsyncSession,
    user: User,
    *,
    planet_slug: str,
    trace_id: str,
    steps_viewed: int,
    total_steps: int,
) -> dict[str, Any]:
    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if planet is None:
        return {"ok": False, "detail": "planet not found"}
    mastery = await gates.ensure_mastery(session, user.id, planet.id)
    ratio = (steps_viewed / total_steps) if total_steps else 0
    detail = f"演武 {trace_id} 观看 {steps_viewed}/{total_steps}"
    snap = gates.record_learn_evidence(
        mastery,
        kind="algo_viz",
        ref_id=trace_id,
        detail=detail,
        auto_pass_learn=ratio >= 0.8,
    )
    await session.commit()
    return {"ok": True, "ratio": round(ratio, 3), "gates": snap}


async def predict_next_state(
    session: AsyncSession,
    user: User,
    *,
    trace_id: str,
    step_index: int,
    answer: str,
    planet_slug: str = "",
) -> dict[str, Any]:
    """预测下一步状态：答对则记用闸 credit。"""
    trace = get_trace(trace_id)
    if not trace:
        return {"ok": False, "correct": False, "detail": "轨迹不存在"}
    steps = trace.get("steps") or []
    if step_index < 0 or step_index >= len(steps):
        return {"ok": False, "correct": False, "detail": "步骤索引无效"}
    step = steps[step_index] if isinstance(steps[step_index], dict) else {}
    predict = step.get("predict") if isinstance(step.get("predict"), dict) else None
    if not predict:
        # 轻量 stub：无 predict 字段时，用下一步 narrate/bars 作为期望答案提示
        nxt = steps[step_index + 1] if step_index + 1 < len(steps) and isinstance(steps[step_index + 1], dict) else {}
        expected = str(nxt.get("narrate") or nxt.get("bars") or "").strip()
        question = "请预测下一步会发生什么？"
        options: list = []
        answer_key = expected
    else:
        question = str(predict.get("question") or "预测下一状态")
        options = list(predict.get("options") or [])
        answer_key = str(predict.get("answer") or predict.get("answer_key") or "").strip()
        expected = answer_key

    given = str(answer or "").strip()
    correct = False
    if answer_key:
        # 支持选项 key（A/B/C）或全文匹配
        correct = given.upper() == answer_key.upper() or given == expected
        if not correct and options:
            for opt in options:
                if isinstance(opt, dict) and str(opt.get("key", "")).upper() == answer_key.upper():
                    if given == str(opt.get("text") or "") or given.upper() == str(opt.get("key") or "").upper():
                        correct = True
                    break

    result: dict[str, Any] = {
        "ok": True,
        "correct": correct,
        "question": question,
        "expected": answer_key,
        "apply_credit": False,
        "gates": None,
        "lit": False,
    }
    if not correct or not planet_slug:
        return result

    planet = (await session.execute(select(Planet).where(Planet.slug == planet_slug))).scalar_one_or_none()
    if planet is None:
        result["detail"] = "行星不存在，未计入用闸"
        return result

    mastery = await gates.ensure_mastery(session, user.id, planet.id)
    # 确保 apply_required 与挑战逻辑一致（代码行星强制用闸）
    tags = list(getattr(planet, "tags", None) or [])
    if isinstance(tags, str):
        tags = [tags]
    codeish = any(t in tags for t in ("code", "coding", "编程", "算法实现")) or getattr(planet, "difficulty", "") == "hard"
    gates.set_apply_required(mastery, bool(codeish))
    snap = gates.apply_credit(
        mastery,
        source=f"{trace_id}@{step_index}",
        detail=f"演武预测答对 · {trace_id} step {step_index}",
    )
    lit = False
    if snap.get("apply_passed"):
        lit = gates.try_light_planet(mastery)
        if lit:
            user.points += 10
            session.add(user)
    await session.commit()
    result["apply_credit"] = bool(snap.get("apply_credit"))
    result["apply_passed"] = bool(snap.get("apply_passed"))
    result["apply_required"] = bool(snap.get("apply_required", True))
    result["gates"] = snap
    result["lit"] = lit
    if snap.get("hint"):
        result["detail"] = snap["hint"]
    return result


def _bubble_trace(arr: list[int], title: str = "冒泡排序（自定义数据）") -> dict[str, Any]:
    a = list(arr)
    steps: list[dict[str, Any]] = [
        {
            "line": 1,
            "narrate": f"初始数组 {a}",
            "vars": {"arr": list(a)},
            "stack": ["bubble_sort"],
            "bars": list(a),
            "highlight": [],
        }
    ]
    n = len(a)
    for i in range(n):
        for j in range(0, n - i - 1):
            steps.append(
                {
                    "line": 4,
                    "narrate": f"比较 a[{j}]={a[j]} 与 a[{j+1}]={a[j+1]}",
                    "vars": {"i": i, "j": j, "arr": list(a)},
                    "stack": ["bubble_sort", "compare"],
                    "bars": list(a),
                    "highlight": [j, j + 1],
                }
            )
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                steps.append(
                    {
                        "line": 5,
                        "narrate": f"交换 → {a}",
                        "vars": {"i": i, "j": j, "arr": list(a)},
                        "stack": ["bubble_sort", "swap"],
                        "bars": list(a),
                        "highlight": [j, j + 1],
                    }
                )
    steps.append(
        {
            "line": 6,
            "narrate": f"排序完成 {a}",
            "vars": {"arr": list(a)},
            "stack": ["bubble_sort"],
            "bars": list(a),
            "highlight": list(range(len(a))),
        }
    )
    return {
        "id": f"custom-bubble-{uuid.uuid4().hex[:8]}",
        "title": title,
        "structure": "array",
        "code": "def bubble_sort(arr):\n    n = len(arr)\n    for i in range(n):\n        for j in range(0, n - i - 1):\n            if arr[j] > arr[j + 1]:\n                arr[j], arr[j + 1] = arr[j + 1], arr[j]\n    return arr\n",
        "steps": steps,
        "planet_keywords": ["排序", "冒泡"],
    }


def _bst_layout(values_in_order: list[int]) -> tuple[list[dict], list[list[str]]]:
    """简单层序布局：按插入顺序建树后给坐标。"""

    class N:
        def __init__(self, v: int):
            self.v = v
            self.l: N | None = None
            self.r: N | None = None

    root: N | None = None

    def insert(v: int) -> None:
        nonlocal root
        if root is None:
            root = N(v)
            return
        cur = root
        while True:
            if v < cur.v:
                if cur.l is None:
                    cur.l = N(v)
                    return
                cur = cur.l
            else:
                if cur.r is None:
                    cur.r = N(v)
                    return
                cur = cur.r

    for v in values_in_order:
        insert(v)

    nodes: list[dict] = []
    edges: list[list[str]] = []

    def walk(node: N | None, x: float, y: float, span: float, pid: str | None = None) -> None:
        if node is None:
            return
        nid = f"n{node.v}"
        nodes.append({"id": nid, "label": str(node.v), "x": x, "y": y})
        if pid:
            edges.append([pid, nid])
        walk(node.l, x - span, y + 0.18, span * 0.55, nid)
        walk(node.r, x + span, y + 0.18, span * 0.55, nid)

    walk(root, 0.5, 0.12, 0.22)
    return nodes, edges


def _bst_insert_trace(seq: list[int], title: str = "二叉搜索树插入（自定义）") -> dict[str, Any]:
    built: list[int] = []
    steps: list[dict[str, Any]] = [
        {
            "line": 1,
            "narrate": f"准备依次插入 {seq}",
            "vars": {"seq": str(seq)},
            "stack": ["<module>"],
            "nodes": [],
            "edges": [],
            "highlight": [],
        }
    ]
    for v in seq:
        built.append(v)
        nodes, edges = _bst_layout(built)
        steps.append(
            {
                "line": 8,
                "narrate": f"插入 {v}，当前树节点 {built}",
                "vars": {"val": v, "seq": str(built)},
                "stack": ["insert"],
                "nodes": nodes,
                "edges": edges,
                "highlight": [f"n{v}"],
            }
        )
    return {
        "id": f"custom-bst-{uuid.uuid4().hex[:8]}",
        "title": title,
        "structure": "tree",
        "code": "class Node:\n    def __init__(self, v):\n        self.v, self.l, self.r = v, None, None\n\ndef insert(root, v):\n    if root is None:\n        return Node(v)\n    if v < root.v:\n        root.l = insert(root.l, v)\n    else:\n        root.r = insert(root.r, v)\n    return root\n",
        "steps": steps,
        "planet_keywords": ["二叉树", "BST"],
    }


def rerun_from_initial(
    *,
    structure: str,
    initial: dict[str, Any],
    code: str = "",
    title: str = "",
) -> dict[str, Any]:
    """可视化修改后重跑：对 array/tree/graph 用确定性轨迹引擎（零幻觉）。"""
    structure = (structure or "array").lower()
    if structure == "graph":
        algo = str(initial.get("algo") or "").lower()
        if _is_dijkstra_topic(algo, title):
            t = _dijkstra_trace(initial, title or "Dijkstra（重跑）")
        elif _is_dfs_topic(algo, title):
            t = _graph_dfs_trace(initial, title or "DFS（重跑）")
        else:
            t = _graph_bfs_trace(initial, title or "BFS（重跑）")
    elif structure == "tree":
        seq = initial.get("seq") or initial.get("values") or initial.get("arr") or [8, 3, 10, 1, 6]
        seq = [int(x) for x in seq][:12]
        t = _bst_insert_trace(seq, title or "BST 插入（重跑）")
    else:
        arr = initial.get("arr") or initial.get("bars") or initial.get("values") or [5, 2, 9, 1, 6]
        arr = [int(x) for x in arr][:16]
        t = _bubble_trace(arr, title or "冒泡排序（重跑）")
    if code.strip():
        t["code"] = code
    t["editable"] = True
    t["initial"] = initial
    return t


async def generate_trace(topic: str, planet_slug: str = "") -> dict[str, Any]:
    """DeepSeek 生成 VizTrace；失败回退种子包或本地引擎。"""
    topic = (topic or "").strip() or "冒泡排序"
    prompt = f"""你是 VizAgent。为学生演示知识点「{topic}」（行星 slug: {planet_slug or 'n/a'}）。
严格返回 JSON（不要 markdown）：
{{
  "id": "ai-xxx",
  "title": "短标题",
  "structure": "array 或 tree 或 graph",
  "code": "可演示的 Python 代码字符串",
  "steps": [
    {{
      "line": 1,
      "narrate": "本步讲解",
      "vars": {{}},
      "stack": ["main"],
      "bars": [3,1,4] ,
      "nodes": [{{"id":"n1","label":"1","x":0.5,"y":0.2}}],
      "edges": [["n1","n2"]],
      "highlight": [0]
    }}
  ],
  "planet_keywords": ["关键词"]
}}
规则：
- structure=array 时每步必须有 bars（数字数组），nodes/edges 可空
- structure=tree 或 graph 时每步必须有 nodes（含 id/label/x/y，x/y 在 0~1）与 edges
- structure=graph 时 edges 可为 [u,v] 或加权 [u,v,w]；highlight 可为节点 id 或边键 "u-v"
- steps 4~12 步，narrate 用中文
- highlight 指向当前关注的下标或节点 id
"""
    raw = await spark_chat(
        [
            {"role": "system", "content": "你是演武舱 VizAgent，只返回合法 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
    )
    data = extract_json(raw) if raw else None
    if isinstance(data, dict) and data.get("steps") and _validate_trace(data):
        data.setdefault("id", f"ai-{uuid.uuid4().hex[:8]}")
        data.setdefault("title", topic)
        data.setdefault("structure", "array")
        data.setdefault("code", "# generated")
        data["source"] = "deepseek"
        return data

    # 回退：关键词匹配种子，或本地引擎
    graph_kw = ("图", "BFS", "DFS", "最短路", "Dijkstra", "dijkstra", "广度", "深度")
    if any(k in topic for k in graph_kw):
        t = _graph_engine_fallback(topic)
        t["source"] = "engine_fallback"
        return t

    matched = match_trace_for_planet(topic, topic)
    if matched:
        out = dict(matched)
        out["id"] = f"fallback-{out.get('id', 'seed')}"
        out["title"] = f"{topic}（种子回退）"
        out["source"] = "seed_fallback"
        return out
    if any(k in topic for k in ("树", "BST", "二叉", "插入")):
        t = _bst_insert_trace([8, 3, 10, 1, 6], f"{topic}（本地引擎）")
    elif any(k in topic for k in graph_kw):
        t = _graph_engine_fallback(topic)
    else:
        t = _bubble_trace([5, 2, 9, 1, 6], f"{topic}（本地引擎）")
    t["source"] = "engine_fallback"
    return t
