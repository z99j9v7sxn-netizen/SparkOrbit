# SparkOrbit Better Harness 报告

生成时间：`2026-08-12T14:19:02.809198+00:00`  
状态：`ok` · 总分：**100**（15/15 项证据已观察）

## 五维

- **Agent 可观测**: 90（observed）
- **鉴权会话**: 85（observed）
- **教学闭环**: 80（observed）
- **迁移基线**: 85（observed）
- **证据包**: 100（observed）

## 发现

- [observed] **Agent 边界与验收约定** — `AGENTS.md`  
  Cause: 已落盘：AGENTS.md | Expected: 仓库根有 AGENTS.md，写明 mode 与验收 | Repair: 保持现状；随功能演进更新证据。
- [observed] **AgentRun/Step 落库** — `backend/app/services/agent_trace.py`  
  Cause: 已落盘：backend/app/services/agent_trace.py | Expected: agent_runs / agent_steps 可按 user_id 查询 | Repair: 保持现状；随功能演进更新证据。
- [observed] **资源工坊 workflow** — `backend/app/services/resource_agents.py`  
  Cause: 已落盘：backend/app/services/resource_agents.py | Expected: C2 三组 DAG 并行并写 AgentStep | Repair: 保持现状；随功能演进更新证据。
- [observed] **镜像 handoff / council** — `backend/app/services/simulation.py`  
  Cause: 已落盘：backend/app/services/simulation.py | Expected: handoff/council 写 AgentStep | Repair: 保持现状；随功能演进更新证据。
- [observed] **伴学 supervisor** — `backend/app/services/companion_supervisor.py`  
  Cause: 已落盘：backend/app/services/companion_supervisor.py | Expected: supervise 意图→路径/资源/闪卡 | Repair: 保持现状；随功能演进更新证据。
- [observed] **遗忘衰减与复习派发** — `backend/app/services/memory_decay.py`  
  Cause: 已落盘：backend/app/services/memory_decay.py | Expected: scan_and_dispatch_reviews 可派发 DailyTask | Repair: 保持现状；随功能演进更新证据。
- [observed] **教师学情 / CSV** — `backend/app/services/teacher_extras.py`  
  Cause: 已落盘：backend/app/services/teacher_extras.py | Expected: roster import 与 grades export | Repair: 保持现状；随功能演进更新证据。
- [observed] **JWT / 密码哈希** — `backend/app/core/security.py`  
  Cause: 已落盘：backend/app/core/security.py | Expected: create_access_token / resolve_user_id_from_token | Repair: 保持现状；随功能演进更新证据。
- [observed] **Alembic 全量基线** — `backend/alembic/versions/20260812_0001_baseline.py`  
  Cause: 已落盘：backend/alembic/versions/20260812_0001_baseline.py | Expected: upgrade() 用 metadata.create_all | Repair: 保持现状；随功能演进更新证据。
- [observed] **管理端 Agent 回放** — `frontend/src/views/admin/AdminAgents.vue`  
  Cause: 已落盘：frontend/src/views/admin/AdminAgents.vue | Expected: /admin/agents 可筛 mode/status/user | Repair: 保持现状；随功能演进更新证据。
- [observed] **Harness 只读页** — `frontend/src/views/admin/AdminHarness.vue`  
  Cause: 已落盘：frontend/src/views/admin/AdminHarness.vue | Expected: 五维图 + Cause/Expected/Repair 卡片 | Repair: 保持现状；随功能演进更新证据。
- [observed] **闸门策略与复习扫描** — `frontend/src/components/teacher/GatePolicyPanel.vue`  
  Cause: 已落盘：frontend/src/components/teacher/GatePolicyPanel.vue | Expected: GatePolicyPanel 触发 review-scan | Repair: 保持现状；随功能演进更新证据。
- [observed] **评估→路径→资源闭环** — `backend/app/services/learning_loop.py`  
  Cause: 已落盘：backend/app/services/learning_loop.py | Expected: closed-loop/run 可一键补强 | Repair: 保持现状；随功能演进更新证据。
- [observed] **JWT 单测** — `backend/tests/test_jwt_auth.py`  
  Cause: 已落盘：backend/tests/test_jwt_auth.py | Expected: test_jwt_auth 通过 | Repair: 保持现状；随功能演进更新证据。
- [observed] **闭环意图单测** — `backend/tests/test_closed_loop.py`  
  Cause: 已落盘：backend/tests/test_closed_loop.py | Expected: test_closed_loop 通过 | Repair: 保持现状；随功能演进更新证据。

## 复现

```bash
python scripts/generate_local_harness_report.py
```
