# 数据存储与备份

## 存储拆分（已定）

| 层 | 存什么 | 位置 |
|----|--------|------|
| MySQL | 用户、星球、笔记元数据、**星库资产元数据**（`star_assets`）、**知识库索引**（`student_vaults` / `vault_files` / `vault_links`）等 | 数据库 |
| 本地文件 | PDF、本地视频、头像、生成媒体、**每用户 Vault（Markdown）** | `backend/uploads/`、`backend/app/static/media/`、`backend/vaults/` |
| ChromaDB | PDF/大纲文本块与向量（RAG） | `backend/chroma_data/` |

**大视频不要以 BLOB 形式写入 MySQL。** 库里只保留 `file_url` / `bilibili_bvid` 等地址字段；播放走静态路径或外链。

星库相关代码：

- 模型：`backend/app/models/star_asset.py`
- 上传写盘：`backend/app/services/upload_service.py`
- API：`/api/starlib/*`

校验脚本（确认元数据在库、文件在盘、无 BLOB 列）：

```powershell
.\.venv\Scripts\python.exe scripts\verify_star_assets.py
```

## 完整备份（三者一起）

缺任一目录都会导致「库里有记录、文件/向量对不上」。

需要一并备份：

1. **MySQL**：`sparkorbit` 库 dump  
2. **上传与静态媒体**：`backend/uploads/`、`backend/app/static/media/`  
3. **向量库**：`backend/chroma_data/`  
4. **知识库 Vault**：`backend/vaults/`（每用户 Markdown 双链库）

本机 Obsidian 增量同步（可选）：

```powershell
$env:SPARKORBIT_TOKEN="登录后的JWT"
$env:SPARKORBIT_API="http://127.0.0.1:8000"
$env:SPARKORBIT_VAULT="C:\path\to\解压后的Vault"
.\.venv\Scripts\python.exe scripts\obsidian_sync_agent.py
```

### 一键备份

在项目根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup_data.ps1
```

默认输出到 `backups/sparkorbit_YYYYMMDD_HHMMSS/`，内含：

- `mysql/sparkorbit.sql` — 数据库 dump  
- `uploads/` — 用户上传  
- `media/` — 静态/生成视频  
- `chroma_data/` — RAG 向量  
- `MANIFEST.txt` — 备份清单

可选参数：

```powershell
# 指定输出根目录；若本机 mysql 不在 PATH，可传 -MysqlBin
powershell -ExecutionPolicy Bypass -File scripts\backup_data.ps1 -OutRoot "D:\backups" -MysqlBin "D:\mysql-8.1.0-winx64\bin"
```

连接信息默认从 `backend/.env` 的 `DATABASE_URL` 读取。

### 手动备份示例

```powershell
# 1) MySQL（按本机路径调整 mysql/mysqldump）
mysqldump -uroot -p --databases sparkorbit --default-character-set=utf8mb4 > sparkorbit.sql

# 2) 文件
Copy-Item -Recurse backend\uploads .\backup_uploads
Copy-Item -Recurse backend\app\static\media .\backup_media
Copy-Item -Recurse backend\chroma_data .\backup_chroma
```

### 恢复要点

1. 恢复 MySQL：`mysql -uroot -p < sparkorbit.sql`  
2. 将 `uploads/`、`media/`、`chroma_data/` 拷回对应路径  
3. 重启后端；必要时再跑 `scripts\verify_star_assets.py` 核对 `file_url` 与磁盘文件

## Docker 部署

`docker-compose.yml` 已用独立 volume 挂载：

- `mysql_data`
- `backend_uploads`
- `backend_chroma`
- `backend_media_generated`

备份时应对这些 volume 做 volume backup / 容器内 dump，原则相同：**库 + 上传 + 向量 + 生成媒体**一起留存。

## 规模变大时

若本地视频体积持续增长，可把文件迁到对象存储（OSS/S3/MinIO），**仅把 `file_url` 换成对象 URL**，表结构与「不存 BLOB」约定不变。
