# SparkOrbit Agent 边界与验收

本仓库的业务 Agent 运行在 FastAPI 服务内（资源工坊 / 镜像预演 / 伴学等），不是 Coding Agent 宿主插件。

## 改动边界

- 编排与步骤落库：`backend/app/services/resource_agents.py`、`simulation.py`、`agent_trace.py`
- 观测 API：`GET /api/admin/agent-runs`、`GET /api/admin/agent-runs/{id}`
- 管理端可视化：`frontend/src/views/admin/AdminAgents.vue`
- Better Harness（开发体检）产物：`docs/evidence/better-harness/`；管理端只读页 `/admin/harness`

## 编排模式（学生业务）

| mode | 场景 | 要求 |
|------|------|------|
| `workflow` | 资源生成 | C2 三组 DAG 真并行，写 AgentStep |
| `handoff` | 镜像预演 | LangGraph **真正** `astream`，写 AgentStep |
| `council` | 平行宇宙 | 多策略并行后汇总，写 AgentStep |
| `supervisor` | 伴学/辅导 | `POST /agents/companion/supervise` 或 `supervise=true`；意图→路径/资源/闪卡 |
| `workflow` | 模拟面试准备 | `scene="interview"`：JobAnalyst∥ProfileParser → QuestionPlanner → Q-* 真并行，写 AgentStep |
| `handoff` | 模拟面试单轮 | LangGraph `astream`：AnswerAggregator → MultimodalScorer → FollowUpStrategist |
| `council` | 模拟面试总评 | 求职三官 / 升学三官 `asyncio.gather` 后 CouncilSummarizer |

禁止：只 `compile()` 图却手调节点后对外宣称「全系统 LangGraph」。  
禁止：资源生成文档写并行、代码写顺序 for。

## 验收（Done 定义）

1. 学生触发资源/仿真后，`agent_runs` / `agent_steps` 可按 `user_id` 回放。
2. 管理端 `/admin/agents` 能看到：同学、mode、步骤、当前 Agent、状态。
3. 同组资源 Agent 使用独立 DB session 并行执行（非全局大锁串行）。
4. Better Harness：按 `docs/evidence/better-harness/README.md` 可复现报告；不嵌入学生端运行时。

## 与 Better Harness 的关系

Better Harness 评估的是「用 Cursor/Qoder 写本仓库代码」的工作闭环。  
它不调度 DocAgent/Teacher；学生运行观测走 `/admin/agents`。
