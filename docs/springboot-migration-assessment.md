# SparkOrbit 后端迁移至 Spring Boot — 可行性评估

> 文档性质：评估与建议，**本次不修改任何运行代码**。  
> 评估日期：2026-07-15  
> 现状基线：Python FastAPI + SQLAlchemy async + aiomysql + MySQL

---

## 1. 现状盘点

| 维度 | 现状 |
|------|------|
| Python 源文件 | 约 85 个（`backend/app`） |
| REST 接口 | 约 141 个（`app/api/routes.py`） |
| WebSocket | 3 个业务端点：`/api/ws/asr`、`/api/ws/chat/{room_id}`、`/api/ws/study/{room_id}`（另见自习/聊天推送逻辑） |
| 数据库 | MySQL，SQLAlchemy 2.x async + aiomysql；`create_all` + 轻量 `ALTER TABLE` 迁移 |
| 鉴权 | 简易 `token-{user_id}` 形式，依赖注入 `get_current_user` |
| 外部 AI | DeepSeek（LLM）、通义千问/DashScope（图像卡通化）、讯飞大模型语音识别（WS） |
| 业务域 | 学习星图、画像、自习室、聊天、作业/成绩/考勤/群发、商城、桌宠、通知、错题/笔记等 |

体量判断：**全量重写 ≈ 重建一个中等规模教务+学情产品的后端**，不宜在缺少分阶段验收的情况下一次性切换。

---

## 2. 迁移方式对比

### 方案 A：全量重写（Spring Boot 替换全部 Python）

- **做法**：新建 Java 工程，按模块移植全部 API、模型、三方调用与 WebSocket。
- **优点**：长期栈统一，招聘与运维口径一致。
- **缺点**：工期最长、回归面最大；期间无法与现有 FastAPI 功能并行演进；三方签名/流式协议（讯飞 WS、DeepSeek）必须在 Java 侧重新验证。
- **粗估**：以当前规模，完整功能对等 + 联调，通常按「人月」计（视团队熟悉度），明显高于增量方案。

### 方案 B：增量迁移（推荐起步）

- **做法**：新建 Spring Boot 服务，与现有 FastAPI **短期共存**；网关或 Vite 代理按路径分流（例如 `/api/v2/**` → Java，其余仍走 Python）。
- **优点**：可先做登录/鉴权/用户/班级等「薄、高确定性」模块的 POC；随时可回退；不阻断产品迭代。
- **缺点**：一段时间双栈运维；需约定 token、错误码、DTO 兼容规则。

### 方案 C：保持现状（FastAPI 基线）

- **做法**：继续以 Python 为主，仅在确有组织/合规/团队约束时再评估迁移。
- **优点**：零迁移成本；当前栈已支撑异步 IO 与 AI 流式场景。
- **缺点**：若团队强制以 Java 为主，长期维护压力外移。

---

## 3. 技术选型建议（若走 Spring Boot）

| 层面 | 建议 | 说明 |
|------|------|------|
| 框架 | Spring Boot 3.x + Java 21 | LTS、生态完整 |
| Web | 优先 **Spring MVC + 虚拟线程**；若要强对应现有 async 风格可选 **WebFlux** | WebFlux 学习/排障成本更高；虚拟线程足以覆盖多数 I/O 密集接口 |
| 持久化 | MyBatis-Plus **或** Spring Data JPA | 与现有 SQL/表结构对齐时 MyBatis 更直观；领域模型重时用 JPA |
| WebSocket | Spring 原生 WebSocket（`WebSocketHandler`） | ASR 需透传二进制/文本帧到讯飞，不宜强行套 STOMP |
| 配置 | `application.yml` + 环境变量（对齐现有 `.env` 的 `DEEPSEEK_*` / `XF_*` / `QWEN_*`） | 密钥勿入库 |
| 构建 | Maven 或 Gradle | 与团队惯例一致即可 |

前端兼容要点：

- 保持 `/api` 前缀与既有路径语义，或引入版本前缀并同步改 Vite proxy。
- token 形态优先兼容 `token-{userId}`，避免强迫前端一次大改。

---

## 4. 风险清单

1. **讯飞大模型 ASR**：必须在 Java 中完整复现 HMAC 签名、`header/parameter/payload` 帧结构与 `payload.result.text` 的 base64 解码；旧 v2/iat 对本 AppID 不可用。
2. **DeepSeek / 通义千问**：HTTP 客户端、超时、流式（若用）与错误码映射需重新测试。
3. **异步与连接池**：Python 侧 `AsyncSession` 习惯与 Java 事务边界不同，注意长 WS 会话与 DB 会话生命周期分离。
4. **Schema 漂移**：现有表靠 `create_all` + 手写 `ALTER`；迁移前建议冻结一份权威 DDL，再在 Java 侧用 Flyway/Liquibase 管理。
5. **双写/双读**：增量期若两边都写同一 MySQL，易出现缓存与业务不一致，需明确「模块所有权」边界。
6. **回归成本**：141 个 REST + 多 WS，缺少自动化回归会让切换日变为「手工点一遍产品」。

---

## 5. 推荐路径与后续步骤

**推荐顺序：先方案 B 的 POC，再决定是否扩大到全量（方案 A）。**

建议的可执行下一步（不在本次实施范围内，供立项用）：

1. **POC（1～2 周量级目标）**  
   - Spring Boot 工程脚手架 + 健康检查。  
   - 移植：`/api/auth/login`、`/api/classes`、简易 `token` 校验过滤器。  
   - 前端或代理切一条只读流量验证连通。
2. **边界约定**  
   - 写出「Python 继续拥有」与「Java 接管」的模块表（建议先接管：账号/班级；后接管：教师教务；最后接管：AI/WS）。
3. **验收门槛**  
   - POC 通过后再评估作业/成绩/自习室/ASR；ASR 与自习 WS 建议靠后迁移。
4. **若不做 POC**  
   - 维持方案 C，继续在 FastAPI 上迭代（当前路径成本最低）。

---

## 6. 结论

- **技术上可行**：当前后端无不可迁移的「语言锁死」能力，但规模大、AI/WS 多，全量重写风险高。  
- **组织上建议**：不要直接全量替换；先做 **增量 POC + 文档化边界**，用真实接口回归后再扩大范围。  
- **与近期产品修复的关系**：语音识别已切至讯飞大模型协议、摄像头监督在前端加固——这些逻辑若未来迁 Java，需按新协议与前端契约一并移植，避免回退到旧版 `iat-api.xfyun.cn/v2/iat`。

---

*本文档仅供决策参考，不构成对工期或报价的承诺。*
