# SparkOrbit 星轨学图

多智能体协同的个性化资源生成与学习系统。

技术栈：Vue 3 + Vite + FastAPI + MySQL（可 SQLite 兜底）+ ChromaDB。

---

## 环境要求

| 组件 | 版本建议 |
|------|----------|
| Python | 3.11+（推荐 3.12） |
| Node.js | 18+（推荐 22） |
| MySQL | 8.0（可选；无 MySQL 可用 SQLite） |

---

## 从源码启动（开发模式）

### 1. 后端

```bash
cd backend
copy .env.example .env
# 编辑 .env：至少配置 DATABASE_URL；AI 能力需填写 DEEPSEEK_API_KEY 等

# 若使用 MySQL，先建库：
# CREATE DATABASE sparkorbit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

python -m venv ..\.venv
..\.venv\Scripts\activate
pip install -r requirements.txt
# 空库建全表（推荐；应用启动也会尝试 upgrade）
alembic upgrade head
python run.py
```

后端默认：`http://127.0.0.1:8000`  
API 文档：`http://127.0.0.1:8000/docs`  
健康检查：`http://127.0.0.1:8000/api/health`

启动时会自动初始化演示数据（星系、挑战、演示账号等）。

无 MySQL 时，在 `.env` 中改用：

```env
DATABASE_URL=sqlite+aiosqlite:///./sparkorbit.db
```

### 2. 前端

另开终端：

```bash
cd frontend
npm install
npm run dev
```

前端默认：`https://127.0.0.1:5173`（开发证书自签名，浏览器提示「不安全」时可继续访问）  
`/api` 与 `/static` 已代理到后端 `8000` 端口。

### 3. 生产构建（可选）

```bash
cd frontend
npm run build
npm run preview
```

评委验收优先使用公网 https://wikj.online（见 [公网访问说明.md](公网访问说明.md)）。  
本机无 Docker 一键启动见 [部署说明书.md](部署说明书.md)（`start.bat` + Python + SQLite）。

---

## 演示账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 学生 | `student001` | `123456` |
| 教师 | `teacher001` | `123456` |
| 管理员 | `admin001` | `123456` |

---

## 环境变量说明

模板文件：[`backend/.env.example`](backend/.env.example)。复制为 `backend/.env` 后按需填写。

| 变量 | 用途 |
|------|------|
| `DATABASE_URL` | 数据库连接（MySQL / SQLite） |
| `JWT_SECRET` | JWT 签发密钥（生产务必更换；兼容旧 `token-{id}`） |
| `DEEPSEEK_API_KEY` | 核心 LLM（智能体、判题、Tutor 等） |
| `QWEN_API_KEY` | 数字分身图生图（可选） |
| `XF_APP_ID` / `XF_API_KEY` / `XF_API_SECRET` | 讯飞语音听写与口语评测（可选） |
| `CANTONESE_AI_API_KEY` | 粤语口语（可选） |
| `ARK_API_KEY` / `ARK_SEEDANCE_MODEL` | 火山方舟教学短视频（可选） |

**请勿将含真实密钥的 `.env` 提交或打入源码包。**  
未配置部分 Key 时，对应增值能力不可用；登录、星系浏览、基础页面等仍可验收。配置 DeepSeek 后可完整演示多智能体与资源生成主流程。

---

## 目录结构

```
frontend/         Vue3 前端
backend/          FastAPI 后端
docs/             设计方案与评分证据包
公网访问说明.md   公网验收地址（推荐）
部署说明书.md     本机 bat + SQLite 启动说明
```

---

## 数据存储与备份

业务元数据（含星库 `star_assets`）在 MySQL；PDF/视频等大文件在 `backend/uploads/` 与 `backend/app/static/media/`；RAG 文本在 `backend/chroma_data/`。**不要把大视频以 BLOB 写入数据库。**

详情与备份步骤见 [`docs/storage-and-backup.md`](docs/storage-and-backup.md)。一键备份：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup_data.ps1
```

校验星库元数据与磁盘文件：

```powershell
.\.venv\Scripts\python.exe scripts\verify_star_assets.py
```

## 相关文档

- 设计实现方案：`docs/作品设计实现方案.md`
- 存储与备份：`docs/storage-and-backup.md`
- 评分证据与演示脚本：`docs/evidence/`
- 公网验收：`公网访问说明.md`
- 本机 bat 部署：`部署说明书.md`

## 软杯提交打包

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package_submission.ps1
```

生成文件位于 `submit/`：`17016457源码.zip`、`17016457作品.zip`（内容相同）。  
包内含 `frontend/dist`、`.venv`、`backend/.env`、`start.bat`；**不含** `node_modules`、`docs/`、本 README。评委优先打开 https://wikj.online；本机备选双击 `start.bat`（需 Python 3.11+）。
