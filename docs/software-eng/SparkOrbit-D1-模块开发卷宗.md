# SparkOrbit 星轨学图 — 模块开发卷宗

| 项 | 内容 |
|----|------|
| 项目名称 | SparkOrbit 星轨学图 |
| 文档名称 | 模块开发卷宗 |
| 文档编号 | SparkOrbit-D1 |
| 编制者 | SparkOrbit 团队 |
| 编制日期 | 2026-08-01 |
| 版本 | V3.0（工程级完整版） |
| 密级 | 内部 |

---

## 修改记录

| 版本 | 日期 | 修改人 | 说明 |
|------|------|--------|------|
| V1.0 | 2026-08-01 | SparkOrbit 团队 | 初稿，薄卷宗 |
| V2.0 | 2026-08-01 | SparkOrbit 团队 | 扩展为工程级卷宗：增加核心模块详细卷宗、源代码清单、测试说明与复审结论 |
| V3.0 | 2026-08-14 | SparkOrbit 团队 | 工程级对齐：画像修正为八维；新增 BE-15 模拟面试详细卷宗、BE-16~20 与 FE-15~17；后端 20 模块、前端 17 模块、测试 74 用例 |

---

## 1 引言

### 1.1 编写目的

本卷宗记录 SparkOrbit 各核心模块的标题、状态、负责人、功能说明、设计说明、源代码清单、测试说明与复审结论，供配置管理与评审追踪。其中 BE-01（认知画像）与 BE-02（资源生成）为完整详细卷宗，其余模块提供摘要信息。

### 1.2 参考资料

| 编号 | 资料 |
|------|------|
| [R1] | SparkOrbit-C1 概要设计说明书 |
| [R2] | SparkOrbit-C2 详细设计说明书 |
| [R3] | 模块开发卷宗编写规范.doc |
| [R4] | SparkOrbit-E2 测试分析报告 |

---

## 2 核心模块详细卷宗

### 2.1 BE-01：认知画像模块

#### 2.1.1 模块标识

| 项 | 内容 |
|----|------|
| 模块编号 | BE-01 |
| 模块名称 | 认知画像（Profiling） |
| 开发者 | SparkOrbit 团队 |
| 开发周期 | 2026-07-13 至 2026-07-16（国赛闭环阶段） |

#### 2.1.2 功能说明

本模块负责建立并维护学生的八维认知画像（专业背景、前置知识、认知风格、易错倾向、学习目标、时间弹性、模态偏好、动机水平），支持三种画像采集模式：

1. **对话式引导采集**：通过 StudentMirrorAgent 与学生进行自然语言对话，逐步抽取六个维度的量化值（0–100 或分类标签）。
2. **学习事件自动刷新**：学生完成行星挑战、Tutor 辅导、评估等操作后，ProfileRefresher 根据事件类型自动更新对应维度（如错题集中则易错倾向维度升高）。
3. **教师复核与手动校准**：教师可在工作台查看学生画像详情，对自动采集结果进行人工审核与微调。

#### 2.1.3 设计说明

- **架构模式**：服务层 + 数据访问层，对接 FastAPI 路由 `POST /api/profile/dialogue` 与 `GET /api/profile/{student_id}`。
- **数据模型**：`StudentProfile` ORM 表（`backend/app/models/student_profile.py`），字段涵盖六个维度，支持版本快照（`profile_snapshots` 表）以支持画像变化追溯。
- **算法要点**：对话抽取使用 DeepSeek 大模型，输出结构化 JSON；事件刷新使用加权平均公式，根据事件类型配置不同衰减系数。
- **接口**：SSE 流式推送对话回合与画像更新事件；REST 接口供评估联动回灌。
- **存储分配**：MySQL `student_profiles` 表约 2KB/生；快照表按评估频率增长。

#### 2.1.4 源代码清单

| 文件 | 行数（约） | 说明 |
|------|-----------|------|
| `backend/app/services/profiling.py` | 350 | 对话引导 + 维度抽取核心逻辑 |
| `backend/app/services/profiles.py` | 120 | 画像 CRUD + 快照管理 |
| `backend/app/services/profile_refresh.py` | 180 | 学习事件触发刷新 + 衰减算法 |
| `backend/app/models/student_profile.py` | 80 | ORM 模型定义 |
| `backend/app/api/profiles.py` | 90 | REST 路由 |
| **合计** | **820** | |

#### 2.1.5 测试说明

| 测试族 | 用例数 | 通过 | 关键结论 |
|--------|--------|------|----------|
| 对话引导采集 | 3 | 3 | 八维可正常抽取并落库 |
| 事件刷新 | 2 | 2 | 挑战完成、辅导评分后维度正确更新 |
| 快照与回灌 | 1 | 1 | 评估重排可读取历史快照 |
| API 鉴权 | 1 | 1 | 非教师/本人不可查看他人画像 |

> 详细测试结果见 [SparkOrbit-E2 §3.1](SparkOrbit-E2-测试分析报告.md)

#### 2.1.6 复审结论

| 项 | 结论 |
|----|------|
| 功能完整性 | 通过：三种采集模式均已实现并可在演示环境跑通 |
| 代码质量 | 通过：三层架构清晰，关键分支有注释 |
| 文档一致性 | 通过：与 B1 §3.1、C2 §3.1 口径一致 |
| 性能 | 通过：对话延迟约 1.5–2.5 秒（含大模型推理），可接受 |

---

### 2.2 BE-02：资源生成模块

#### 2.2.1 模块标识

| 项 | 内容 |
|----|------|
| 模块编号 | BE-02 |
| 模块名称 | 多智能体资源生成（Resource Agents） |
| 开发者 | SparkOrbit 团队 |
| 开发周期 | 2026-07-13 至 2026-07-16（国赛闭环）+ 07-29（挑战赛 Seedance 增量） |

#### 2.2.2 功能说明

本模块负责根据学生画像与目标知识点，协作生成多类个性化学习资源。支持 7 种资源类型：

| 类型 | Agent | 说明 |
|------|-------|------|
| 讲解文档 | DocAgent | Markdown 格式，含知识点讲解 + 示例 |
| 思维导图 | MindmapAgent | JSON 节点结构，前端 ECharts 渲染 |
| 练习题 | QuizAgent | 选择题/填空/代码/案例分析四种题型 |
| 拓展阅读 | ReadAgent | 跨学科延伸 + 推荐书单 |
| 教学视频 | MediaAgent | Seedance 1.0 Pro Fast 生成短视频，失败降级 GSAP/本地缓存 |
| 代码实操 | CodeAgent | 可运行代码 + 测试用例 |
| 教学课件 | DeckAgent | 翻页讲解 + TTS + PPTX 导出 |

#### 2.2.3 设计说明

- **编排模式**：`ResourceCoordinator` 接收学生画像 + 行星知识点后，根据画像维度与资源类型匹配策略，调用对应的 sub-Agent 并 SSE 流式推送生成进度。
- **质量评估**：每个资源生成后由 `QualityEvaluator` 自动评分（A/P/C/H 四维度：准确性、画像贴合、完整性、幻觉风险），低分可重试。
- **多模型路由**：Coordinator 支持 DeepSeek / 豆包 / 通义 多模型调度；Media 专走火山方舟 Seedance；TTS 走讯飞。
- **溯源机制**：资源记录关联教材页码与知识点 ID，供 Evaluator 交叉验证。

#### 2.2.4 源代码清单

| 文件 | 行数（约） | 说明 |
|------|-----------|------|
| `backend/app/services/resource_agents.py` | 650 | Coordinator + 6 类 Agent 生成逻辑 |
| `backend/app/services/resource_quality.py` | 200 | 质量评分 + 重试控制 |
| `backend/app/services/seedance_service.py` | 150 | Seedance API 对接 + 下载落盘 |
| `backend/app/models/generated_resource.py` | 90 | ORM + 溯源字段 |
| `backend/app/api/resources.py` | 130 | SSE 流式 + CRUD 路由 |
| **合计** | **1,220** | |

#### 2.2.5 测试说明

| 测试族 | 用例数 | 通过 | 关键结论 |
|--------|--------|------|----------|
| 六类资源生成 | 6 | 6 | 每类均可生成并落库可回看 |
| 教学课件生成 | 1 | 1 | deck + TTS + PPTX 导出正常 |
| 质量评分 | 2 | 2 | DeepSeek 自动评分与人工评估一致率达 85% |
| 降级处理 | 1 | 1 | Seedance 不可用时正确降级 GSAP/缓存 |
| SSE 流式 | 1 | 1 | 前端实时展示多 Agent 过程 |

> 详细测试结果见 [SparkOrbit-E2 §3.2](SparkOrbit-E2-测试分析报告.md) 及 [evidence/resource_cases.md](../evidence/resource_cases.md)

#### 2.2.6 复审结论

| 项 | 结论 |
|----|------|
| 功能完整性 | 通过：7 类资源均可生成，含多模态视频与代码 |
| 代码质量 | 通过：Agent 模式 + 工厂解耦，可扩展 |
| 文档一致性 | 通过：与 B1 §3.2、C2 §3.2 口径一致 |
| 性能 | 通过：单资源生成约 8–15 秒（含大模型推理 + Seedance 视频合成） |

---

### 2.3 BE-15：模拟面试模块

#### 2.3.1 模块标识

| 项 | 内容 |
|----|------|
| 模块编号 | BE-15 |
| 模块名称 | 模拟面试（Mock Interview） |
| 开发者 | SparkOrbit 团队 |
| 开发周期 | 2026-08-13 至 2026-08-14（面试与求职增量阶段） |

#### 2.3.2 功能说明

本模块覆盖求职（job）/ 升学（academic）双场景模拟面试全流程，采用三模式多智能体编排：

1. **准备阶段（workflow）**：`JobAnalyst ∥ ProfileParser` → `QuestionPlanner` → `Q-*` 四类出题官，组内 `asyncio.gather` 真并行出题，产出岗位情报/考察主题/候选人画像。
2. **单轮评分（handoff）**：`AnswerAggregator → MultimodalScorer → FollowUpStrategist`，LangGraph `astream` 真流式评分。
3. **总评（council）**：求职三官（技术官/HR官/业务官）或升学三官并行评议后汇总。

另含练习舱（STAR 四要素快练）、能力画像（五维雷达 + 弱项闭环回流）、教师督导（任务下发 + 报告点评写回）。

#### 2.3.3 设计说明

- **评分融合**：语义 70% + 韵律 15% + 仪态 15%，缺失模态自动降级并标记 `degraded_modalities`。
- **多模态评分**：语义（LLM）、韵律（音频静音段/语速）、仪态（视觉模型取每轮前 4 帧关键帧，有帧预算）。
- **实时通信**：`interview_ws.py` WebSocket 承载语音流（讯飞 IAT 分帧转写）与关键帧采集。
- **数据模型**：`interview_sessions` / `interview_turns` / `interview_reports` / `interview_practice_records` / `interview_applications`（`backend/app/models/mock_interview.py`）。
- **编排观测**：三类编排均写 `agent_runs` / `agent_steps`，管理端 `/admin/agents` 可回放。

#### 2.3.4 源代码清单

| 文件 | 行数（约） | 说明 |
|------|-----------|------|
| `backend/app/services/interview_agents.py` | 400 | 三模式编排（workflow/handoff/council） |
| `backend/app/services/interview_scoring.py` | 300 | 多模态评分与融合 |
| `backend/app/services/interview_service.py` | 350 | 会话/报告/画像/教师审阅 |
| `backend/app/services/interview_ws.py` | 320 | 实时语音/关键帧/评分 |
| `backend/app/services/interview_practice.py` | 150 | 练习舱 |
| `backend/app/services/interview_applications.py` | 180 | 投递看板 |
| `backend/app/services/interview_resume.py` | 200 | 简历解析/优化/匹配 |
| `backend/app/services/resume_export.py` | 150 | 简历导出（HTML/MD/DOCX） |
| `backend/app/services/interview_catalog.py` | 120 | 岗位角色库 |
| `backend/app/services/interview_transcript.py` | 100 | 转写组装 |
| `backend/app/services/interview_closed_loop.py` | 120 | 弱项闭环回流 |
| `backend/app/models/mock_interview.py` | 150 | ORM 模型 |
| `backend/app/api/interview_routes.py` | 250 | REST 路由 |
| **合计** | **~2,790** | |

#### 2.3.5 测试说明

| 测试族 | 用例数 | 通过 | 关键结论 |
|--------|--------|------|----------|
| 面试会话配置 | 2 | 2 | 求职/升学双场景创建 |
| 准备编排 | 2 | 2 | 三组 DAG 真并行出题 |
| 单轮评分 | 2 | 2 | 多模态融合分正确 |
| 报告总评 | 2 | 2 | 三视角评议生成 |
| **合计** | **8** | **8** | |

> 详细测试结果见 [SparkOrbit-E2 §3.8](SparkOrbit-E2-测试分析报告.md)

#### 2.3.6 复审结论

| 项 | 结论 |
|----|------|
| 功能完整性 | 通过：三模式编排 + 多模态评分 + 练习舱 + 画像 + 教师督导均已实现 |
| 代码质量 | 通过：编排层与评分层解耦，异常回退路径完整 |
| 文档一致性 | 通过：与 B1 §3.1.11、C2 §3.9 口径一致 |
| 性能 | 通过：单轮评分约 3–6 秒（含多模态推理），可接受 |

---

## 3 其他模块摘要卷宗

### 3.1 后端服务模块总览

| 编号 | 模块 | 文件 | 负责人 | 状态 | 测试通过 | 对应 C2 |
|------|------|------|--------|------|----------|---------|
| BE-01 | 认知画像 | profiling.py / profiles.py / profile_refresh.py | 后端 | 完成 | 7/7 | §3.1 |
| BE-02 | 资源生成 | resource_agents.py / resource_quality.py / seedance_service.py | 后端 | 完成 | 11/11 | §3.2 |
| BE-03 | 学习路径 | learning_path.py | 后端 | 完成 | 3/3 | §3.3 |
| BE-04 | 四闸挑战 | challenge.py / mastery_gates.py / gate_policy.py | 后端 | 完成 | 5/5 | §3.4 |
| BE-05 | Shield 防控 | shield.py / hallucination_guard.py / hallucination_tickets.py | 后端 | 完成 | 4/4 | §3.5 |
| BE-06 | WS/SSE | api/ws.py | 后端 | 完成 | 2/2 | §3.6 |
| BE-07 | Vault/RAG | vault_service.py / rag.py | 后端 | 完成 | 3/3 | §3.7 |
| BE-08 | 智能辅导 | ai_tutor.py / digital_tutor.py | 后端 | 完成 | 4/4 | §3.8 |
| BE-09 | 用户管理 | auth.py / users.py | 后端 | 完成 | 3/3 | — |
| BE-10 | 课程星系 | galaxy.py / planets.py | 后端 | 完成 | 2/2 | — |
| BE-11 | 社交聊天 | chat_room.py / social.py | 后端 | 完成 | 2/2 | — |
| BE-12 | 自习督导 | study_room.py / focus_sessions.py | 后端 | 完成 | 2/2 | — |
| BE-13 | 镜像预演 | simulation.py / remediation.py | 后端 | 完成 | 2/2 | — |
| BE-14 | API 日志 | api_log.py / system_settings.py | 后端 | 完成 | 1/1 | — |
| BE-15 | 模拟面试 | interview_agents.py / interview_scoring.py / interview_service.py / interview_ws.py | 后端 | 完成 | 8/8 | §3.9 |
| BE-16 | 求职助手 | interview_applications.py / interview_resume.py / resume_export.py | 后端 | 完成 | 4/4 | §3.10 |
| BE-17 | 教师套件 | teacher_suite.py | 后端 | 完成 | 4/4 | §3.11 |
| BE-18 | 考级中心 | exam_center.py | 后端 | 完成 | 3/3 | §3.12 |
| BE-19 | SRS 复习 | review_queue.py | 后端 | 完成 | 2/2 | §3.12 |
| BE-20 | 编排观测 | agent_trace.py | 后端 | 完成 | 2/2 | — |

### 3.2 前端组件模块总览

| 编号 | 模块 | 目录 | 负责人 | 状态 |
|------|------|------|--------|------|
| FE-01 | 学生学习区 | frontend/src/views/learning/ | 前端 | 完成 |
| FE-02 | 教师工作台 | frontend/src/views/teacher/ | 前端 | 完成 |
| FE-03 | 管理员控制台 | frontend/src/views/admin/ | 前端 | 完成 |
| FE-04 | 登录/认证 | frontend/src/views/auth/ | 前端 | 完成 |
| FE-05 | 星轨领航台 | frontend/src/views/RocketDashboard.vue | 前端 | 完成 |
| FE-06 | 资源工坊 | frontend/src/components/ResourceStudio.vue | 前端 | 完成 |
| FE-07 | 画像对话 | frontend/src/components/ProfileChat.vue | 前端 | 完成 |
| FE-08 | AI 辅导 | frontend/src/components/TutorLab.vue | 前端 | 完成 |
| FE-09 | 休闲/桌宠 | frontend/src/views/leisure/ | 前端 | 完成 |
| FE-10 | 演武舱 | frontend/src/components/AlgoVizLab.vue | 前端 | 完成 |
| FE-11 | 代码舱 | frontend/src/components/CodeLab.vue | 前端 | 完成 |
| FE-12 | 星库 | frontend/src/components/StarLibrary.vue | 前端 | 完成 |
| FE-13 | 自习督导 | frontend/src/views/study-hall/ | 前端 | 完成 |
| FE-14 | 数字人 | frontend/src/components/DigitalTutor.vue | 前端 | 完成 |
| FE-15 | 模拟面试区 | frontend/src/components/interview/ | 前端 | 完成 |
| FE-16 | 求职助手 | frontend/src/components/interview/career/ | 前端 | 完成 |
| FE-17 | 教师面试督导 | frontend/src/components/teacher/InterviewReviewPanel.vue | 前端 | 完成 |

---

## 4 完成状态汇总

| 类别 | 总数 | 完成 | 完成率 |
|------|------|------|--------|
| 后端服务 | 20 | 20 | 100% |
| 前端组件 | 17 | 17 | 100% |
| 后端测试用例 | 74 | 74 | 100% |
| **合计** | **111** | **111** | **100%** |

---

## 5 复审总结论

| 项 | 结论 |
|----|------|
| 所有模块是否按设计完成 | 是（37 个模块全部验收通过） |
| 测试是否验证全部功能 | 是（74 个测试用例全部通过，详见 E2 测试分析报告） |
| 是否满足交付基线 | 是（与 A2 开发计划 / C1 概要设计 / C2 详细设计一致） |
| 缺陷遗留 | 无高优缺陷；低优体验优化项见 F2 总结报告 §4.3 |

---

> **版本**：V3.0 | **编制日期**：2026-08-14 | **文档编号**：SparkOrbit-D1
