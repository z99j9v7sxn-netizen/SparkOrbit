# Better Harness 落地（开发侧）

本目录存放 **只读** 体检产物，供管理端 `/admin/harness` 展示。

## 一键复现（推荐）

```powershell
# 仓库根目录；会 clone/npm CLI、跑官方探测，并生成管理端字段对齐的 findings
powershell -ExecutionPolicy Bypass -File scripts/run_better_harness.ps1
```

产物至少包含：

| 文件 | 说明 |
|------|------|
| `findings.json` | `status=ok`，每条含 `dimension/cause/expected/repair` |
| `report.html` / `report.md` | 非 Placeholder 可读报告 |
| `cli-report-probe.txt` | 官方 `better-harness report` 探测日志 |
| `cli-analyze.json` | 官方 `harness analyze --json` 证据包 |

## 仅本地扫描器（零 Node 依赖）

```bash
python scripts/generate_local_harness_report.py
python scripts/normalize_harness_findings.py
```

## 说明

- 官方 CLI ≥0.5 的 `report` 会把「完整五维结论」交给 IDE skill（`/better-harness`）；本仓库用本地扫描器落管理端契约，CLI 探测/analyze 作为额外证据。
- 管理端 **不会** 在服务器上重跑 Harness；只读本目录。
- `tools/better-harness` 为外部克隆，勿提交。
