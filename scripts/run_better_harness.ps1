#Requires -Version 5.1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$harness = Join-Path $root "tools\better-harness"
$outDir = Join-Path $root "docs\evidence\better-harness"
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

if (-not (Test-Path $harness)) {
  Write-Host "Cloning QoderAI/better-harness into tools/better-harness ..."
  New-Item -ItemType Directory -Force -Path (Join-Path $root "tools") | Out-Null
  git clone --depth 1 https://github.com/QoderAI/better-harness.git $harness
  if (-not (Test-Path $harness)) {
    Write-Error "Clone failed (network?). Keep docs/evidence/better-harness placeholders and retry later."
    exit 1
  }
}

$cli = Join-Path $harness "scripts\better-harness.mjs"
Push-Location $harness
try {
  if (-not (Test-Path "node_modules")) {
    npm ci
  }
} finally {
  Pop-Location
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# 必须在 SparkOrbit 仓库根跑，避免扫到 tools/better-harness 自身
Write-Host "Running official CLI report probe on workspace root ..."
$reportLog = Join-Path $outDir "cli-report-probe.txt"
& node $cli report --no-sessions --workspace $root 2>&1 | Tee-Object -FilePath $reportLog

Write-Host "Running official CLI harness analyze --json ..."
$analyzeJson = Join-Path $outDir "cli-analyze.json"
& node $cli harness analyze --workspace $root --language zh --format json 2>&1 | Set-Content -Path $analyzeJson -Encoding utf8

# 拷贝 CLI 若写出的静态产物
$candidates = @(
  (Join-Path $harness "report.html"),
  (Join-Path $harness "report.md"),
  (Join-Path $harness "findings.json"),
  (Join-Path $harness "dist\report.html"),
  (Join-Path $harness "dist\findings.json"),
  (Join-Path $root ".better-harness\report.html"),
  (Join-Path $root ".better-harness\findings.json"),
  (Join-Path $root "report.html"),
  (Join-Path $root "findings.json")
)
foreach ($f in $candidates) {
  if (Test-Path $f) {
    Copy-Item $f $outDir -Force
    Write-Host "Copied $f -> $outDir"
  }
}

# 管理端契约产物：本地扫描器保证非占位 + Cause/Expected/Repair
Write-Host "Generating AdminHarness-shaped findings (local scanner) ..."
& $py (Join-Path $root "scripts\generate_local_harness_report.py")
& $py (Join-Path $root "scripts\normalize_harness_findings.py")

Write-Host "Done. Open admin /admin/harness or check $outDir"
Write-Host "CLI probe: $reportLog"
Write-Host "CLI analyze: $analyzeJson"
