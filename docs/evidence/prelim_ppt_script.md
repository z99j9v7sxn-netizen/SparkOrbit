# SparkOrbit 初赛方案 PPT 制作说明书

> 用途：讯飞 AI 开发者大赛 / Adaptive-LPDS「方案 PPT」  
> 配套产出：`submit/SparkOrbit_初赛方案PPT.pptx`（同步覆盖桌面 `星轨学图图片版.pptx`）  
> 生成脚本：`scripts/build_prelim_pptx.py`  
> 必覆盖：场景来源 · 用户痛点 · 核心流程 · 产品形态 · Agent 能力 · 工具/数据/模型 · 合规边界 · 后续落地计划  
> 改稿原则：一页一主张 · 真截图优先 · 六维 / 七 Agent / 四模式 / Shield 三级 / 四闸写进画面  
> 页数：12 页（封面 + 必写 8 章 + 差异化 + 模拟面试 + 复现致谢）

---

## 一、视觉规范

| 用途 | 色值 |
|------|------|
| 背景深 | `#0B1220` |
| 背景浅 | `#F4F7FB` |
| 主文字（深底） | `#E8EEF7` |
| 主文字（浅底） | `#1A2332` |
| 强调色 | `#3DB8A0` |
| 次强调（注意/合规） | `#E8A838` |
| 弱文字 | `#6B7C93` |
| 描边 | `#D0D7E2` |

字体：中文微软雅黑；英文/代码 Consolas。  
页脚：左 `SparkOrbit 星轨学图` · 右 `页码`。  
纪律：每页一句主张（claim）；忌紫粉渐变与空话排比；截图须为真界面；禁止穿戴/手表等无关模板图。  
不写：Better Harness、桌宠/休闲细节、「全系统 LangGraph」、LMS 已对接、等保已过。

---

## 二、逐页文案（12 页）

---

### 第 1 页 · 封面

**主张：** 差异化一句说清，不是「又一个闭环口号」。

- 主标题：SparkOrbit 星轨学图
- 副标题：认知孪生驱动的多智能体学习系统：作答前预演 · 四闸掌握 · 求职/升学面试闭环
- 场景标签：高等教育 · 数据结构 / 机器学习 · Adaptive-LPDS
- 团队：爱拼才慧莹 · 吉林外国语大学 · 演示站 https://wikj.online
- 差异主张条：预演仿真 · 四模式 Agent · 四闸掌握 · Shield 终裁

**口播（约 15s）：**  
「评委老师好，我们是爱拼才慧莹队。星轨学图用多智能体在作答前预演误区，四闸确认学会，并把低置信结果交给教师终裁；出口场景还能走求职/升学面试闭环。」

**配图：** `hub_01.png`（或缺 `resource_media_01.png`）

---

### 第 2 页 · 场景来源（必写）

**主张：** 大班断层 + Chat 学伴缺闭环 + 可信缺口 → 切计算机课做可复现 Web 试点。

- 左三卡：大班现实 / AI 助学现状 / 可信缺口
- 右框：落地切入（学科、用户）+ 适用场景
  - 大班授课：学情风险筛查 + 人审工单
  - 自习助学：画像路径 + 本地督导
  - 编程实训：CodeLab + 演武舱
  - 校本试点：讲义锻造 → 星系图谱
  - **求职校招 / 考研复试：第 7 区模拟面试（本页不展开）**
- **禁止**：占位「一段文字说明」、手表等无关配图

**口播（约 40s）：**  
高等教育大班个性化成本高；现有 Chat 学伴停在问答；选计算机类可结构化课程先落地，便于 Agent、RAG、判题验证。求职与升学作为出口场景，放到第 8 页。

**配图：** `resource_mindmap_01.png`

---

### 第 3 页 · 用户痛点 → 解法映射（必写）

**主张：** 三角色硬痛点立靶；底部标明后文哪一环解。

- 学生
  - 课内：画像粗、资源同质、补救滞后 → 六维 + 四闸 + 路径回灌
  - **出口：面试靠题海、缺多模态评与回流 → 第 8 页三官 council + 错题闭环**
- 教师：难筛风险与低置信 · AI 难信 → 星系锻造 + Shield 工单
- 管理员：Token/运维不可见 · 缺统一台 → 用量监测 + 维护模式 + Agent 观测

**口播（约 45s）：**  
逐角色点两句；解法不在本页展开。

**配图：** `eval_report_01.png`

---

### 第 4 页 · 差异化一览

**主张：** 四条可演示壁垒，评委 10 秒能复述。

1. 预演仿真链（Teacher→Mirror→Evaluator→PathPlanner）
2. 四闸掌握协议（学→练→讲→用）
3. Shield 人审终裁（引用 ID + 置信度 + 工单）
4. **四模式 Agent + 七类校本资源**（workflow / handoff / council / supervisor；Doc/Mind/Quiz/Read/Media/Deck/Code）

每条含：机制句 + 演示入口。模拟面试不在本页抢戏，指向第 8 页。

**口播（约 40s）：**  
压住「不是 Chat 学伴」；后文展开细节。

---

### 第 5 页 · 核心流程（必写）

**主张：** 六维可核对 · 七 Agent 可点名 · 四闸是掌握协议主视觉。

- 主流程六步：对话画像 → 资源生成 → 路径推送 → 智能辅导 → 效果评估 → 教师复核
- 六维：专业背景、前置知识、认知风格、易错倾向、学习目标、时间弹性
- 七 Agent：Doc / Mind / Quiz / Read / Media / **Deck** / Code（Media=Seedance+质量分；Deck=课件/闪卡/PPTX）
- 深色高亮条：学→练→讲→用，证据齐全才算学会
- 脚注：出口场景走第 8 页面试闭环（准备→单轮→总评→回流）
- 路径前后对比截图

**口播（约 50s）：**  
演示与评分只认主链路；面试是出口场景。

**配图：** `path_before_01.png` + `path_after_01.png`

---

### 第 6 页 · 产品形态（必写）

**主张：** 三角色 Web 产品；教师是终裁端；七区里主链路在学习区；休闲答辩 ≤10 秒。

- 交付：SPA · REST+SSE+WS · Docker Compose · 公网 HTTPS
- 学生端七区：学习 / 星域 / 树洞 / 聊天 / 自习 / 休闲 / **模拟面试**
- 学习区 Dock 主链路：星库 · 演武舱 · CodeLab · 资源工坊 · 伴学
- 教师：锻造 · 学情 · 人审 · TimeWarp · **面试督导**
- 管理：用户 / 内容 / 用量 / 维护 · **Agent 运行回放**
- 商业：校本 B2B2C + 可选 B2C/Token

**配图：** `resource_doc_01.png` + `tutor_socratic_01.png`

---

### 第 7 页 · Agent 能力（必写，整页重写）

**主张：** 四种真编排，不是单模型包办；LangGraph 只用于 handoff，勿称全系统都是 LangGraph。

四模式表：

| mode | 场景 | 实际行为 |
|------|------|----------|
| workflow | 资源工坊 / 面试准备 | C2 三组 DAG 真并行，写 AgentStep |
| handoff | 镜像预演 / 面试单轮 | LangGraph 真正 astream |
| council | 平行宇宙 / 面试总评 | 多策略或三官并行后汇总 |
| supervisor | 伴学 | 意图分类 → 路径/资源/闪卡工具 |

代表链：

- 仿真 handoff：Teacher → Mirror → Evaluator → PathPlanner
- 资源 workflow：Doc/Mind/Quiz/Read/Media/Deck/Code，同组独立 DB session 并行

底部 Shield 三级：知识点 ID+RAG → 独立引用/置信 → 低置信进工单；苏/费曼辅导；AI 不终裁。  
观测：管理端 `/admin/agents` 按 user_id 回放步骤。

**配图：** `resource_media_01.png` + `hallu_ticket_teacher_01.png`

---

### 第 8 页 · 模拟面试（大更新主页）

**主张：** 课内闭环的出口场景：求职 / 升学共用四模式 Agent，评完回流错题。

- 双场景：求职校招 / 升学考研复试
- 三阶段
  1. 准备 workflow：JobAnalyst ∥ ProfileParser → QuestionPlanner → Q-* 真并行
  2. 单轮 handoff：AnswerAggregator → MultimodalScorer → FollowUpStrategist
  3. 总评 council：求职三官（技术/HR/业务）或升学三官（学科/素质/科研）
- 产品：数字人 + 讯飞 IAT + 五维雷达 + 弱项追问 + 回流错题/复习卡
- 演示：学生端第 7 区；管理端 `scene=interview` 可回放
- 降级：关麦/关视觉仍可用文本完成，不假装全模态必开

**口播（约 45s）：**  
面试不是另一套聊天框，而是把四模式 Agent 接到就业/升学出口，低分回流学习闭环。

**配图：** `interview_job_text_01.png` / `interview_academic_01.png`（缺图则形状卡片 + 注明现场点验）

---

### 第 9 页 · 工具 / 数据 / 模型（必写）

**主张：** 按任务路由；督导视频不出浏览器。

三列：

- 工具：Vue3 · FastAPI · SSE/WS · ChromaDB · LangGraph（仅 handoff）· AgentRun/Step 落库 · `/admin/agents` 回放
- 数据：六维画像 · 四闸证据 · 路径评估 · 校本向量 · 面试会话/媒体（可删）· Vault 笔记 · 用量日志
- 模型：DeepSeek 推理评分；讯飞星火/IAT/ISE/数字人；Seedance 短视频；通义分身；视觉理解用于面试仪态（降级可文本）

页脚数据流原则：外发仅 prompt / 必要音视频；督导摄像头视频流不出浏览器。

**配图：** `docs/word/img/diagram-2.png`

---

### 第 10 页 · 合规边界（必写）

**主张：** 已实现 vs 未宣称；主动划界。

已实现：

- 自习督导 TF.js 本地推理，视频不出浏览器
- RBAC 三角色；密钥 .env 不进仓库
- Shield 风控；低置信不终裁，教师可覆盖
- **学生删除面试会话 → 媒体与报告一并消失**
- 定位：竞赛演示 + 校本试点基线

未宣称 / 后续增强：

- 完整不可篡改审计库、等保级合规
- 未成年人监护人明示同意
- PDF 页码级强制引用
- LMS 已对接（规划中，不写已上线）

原则条：算法建议可误导 → 人机协同终裁；隐私能本地则本地。

**配图：** `hallu_ticket_teacher_01.png`

---

### 第 11 页 · 后续落地（必写）

**主张：** 先嵌教学流程，再谈跨校生态。

- 近期（6 个月内）：扩充校本 RAG；遗忘阈值班级可配；移动端降级
- 中期（6–18 个月）：对接 LMS / 花名册成绩回写；预演 vs 真答校准；可解释报告
- 长期（18 个月+）：跨校星系共创；多模态加深；校内本地化 / 隐私计算
- 半句：面试闭环先做校本就业/升学辅导试点，再谈跨校题库

---

### 第 12 页 · 进度与复现（含致谢）

**主张：** 按主链路点验；收束预演 · 四闸 · Shield · 面试闭环。

- 已完成：七区 · 七 Agent · 四模式可回放 · 模拟面试主路径 · 四闸/星库/演武/CodeLab · Docker + 公网
- 验证：https://wikj.online · student001 / teacher001 / admin001 · 密码见部署说明 · docs/evidence/
- 谢谢评委 · 预演 · 四闸 · Shield · 面试闭环
- **禁止**：穿戴设备/健康管理等串页文案；勿先点休闲区

**配图：** `eval_report_01.png` + `resource_media_01.png`

---

## 三、截图映射

| 页 | 优先文件 | 备用 |
|----|----------|------|
| 1 | `hub_01.png` | `resource_media_01.png` / `diagram-1.png` |
| 2 | `resource_mindmap_01.png` | `diagram-3.png` |
| 3 | `eval_report_01.png` | — |
| 4 | （形状卡片，无强制图） | — |
| 5 | `path_before_01.png` + `path_after_01.png` | — |
| 6 | `resource_doc_01.png` + `tutor_socratic_01.png` | — |
| 7 | `resource_media_01.png` + `hallu_ticket_teacher_01.png` | — |
| 8 | `interview_job_text_01.png` | `interview_academic_01.png`；缺则形状卡 |
| 9 | `docs/word/img/diagram-2.png` | `diagram-4.png` |
| 10 | `hallu_ticket_teacher_01.png` | — |
| 11 | — | — |
| 12 | `eval_report_01.png` + `resource_media_01.png` | `resource_quiz_01.png` |

缺图时生成脚本回退灰色形状卡并标注槽位名，**不造假 UI**。

---

## 四、提交检查清单

- [x] 场景来源与适用场景合并，含求职/升学一句，无占位字、无关配图
- [x] 差异化一览突出预演 / 四闸 / Shield / 四模式+七 Agent
- [x] 流程页写出六维名与七 Agent 名；四闸为主视觉
- [x] Agent 页写清四模式 + Shield 三级；未宣称全系统 LangGraph
- [x] 新增模拟面试页：准备 / 单轮 / 总评 + 回流
- [x] 合规页含面试媒体可删；未宣称等保/LMS 已对接
- [x] 进度页无穿戴串词；主链路点击路径写死
- [x] 队名、学校已填写
- [x] 未把休闲/桌宠/Better Harness 写成核心
- [ ] 导出 PDF（WPS/PowerPoint「另存为 PDF」）

**建议文件名：** `SparkOrbit_初赛方案PPT.pptx` / 桌面 `星轨学图图片版.pptx`
