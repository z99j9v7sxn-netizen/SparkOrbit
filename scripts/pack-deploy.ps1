# 完整迁移打包：含资料、API .env、运行时数据；排除可重建依赖与 SSH pem
# 用法（项目根）: powershell -ExecutionPolicy Bypass -File .\scripts\pack-deploy.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "docker-compose.yml"))) {
    $Root = Get-Location
}
Set-Location $Root

$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$OutName = "sparkorbit-full-$Stamp.tar.gz"
$OutPath = Join-Path $Root $OutName

$Exclude = @(
    ".venv",
    "submit",
    "backups",
    ".idea",
    "frontend/node_modules",
    "frontend/dist",
    "*.pem",
    "*.log"
)

Write-Host "[pack] root = $Root"
Write-Host "[pack] output = $OutPath"
Write-Host "[pack] excluding: $($Exclude -join ', ')"

if (-not (Test-Path (Join-Path $Root "backend\.env"))) {
    Write-Warning "backend/.env 不存在：服务器上将缺少 API Key"
}
if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Warning "根目录 .env 不存在：将尝试从 .env.example 复制"
    if (Test-Path (Join-Path $Root ".env.example")) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    }
}
if (-not (Test-Path (Join-Path $Root "资料"))) {
    New-Item -ItemType Directory -Path (Join-Path $Root "资料") | Out-Null
}

# tar --exclude 相对路径（在 Root 下打包 .）
$tarArgs = @("-czf", $OutPath)
foreach ($e in $Exclude) {
    $tarArgs += "--exclude=$e"
}
# 额外排除打包产物自身与常见缓存
$tarArgs += "--exclude=sparkorbit-full-*.tar.gz"
$tarArgs += "--exclude=__pycache__"
$tarArgs += "--exclude=*.pyc"
$tarArgs += "--exclude=.git"
$tarArgs += "-C", $Root, "."

& tar @tarArgs
if ($LASTEXITCODE -ne 0) { throw "tar failed: $LASTEXITCODE" }

$item = Get-Item $OutPath
$sizeGB = [math]::Round($item.Length / 1GB, 2)
Write-Host ""
Write-Host "========================================"
Write-Host " 打包完成: $($item.FullName)"
Write-Host " 大小: $sizeGB GB ($([math]::Round($item.Length / 1MB, 1)) MB)"
Write-Host " 下一步: 用 SparkOrbit.pem scp 上传到服务器"
Write-Host " 详见: 服务器部署速查.md"
Write-Host "========================================"
