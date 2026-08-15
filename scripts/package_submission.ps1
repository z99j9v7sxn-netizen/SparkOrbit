# 打包软杯「源码包」与「作品包」（公网优先说明 + 本机 bat/SQLite，无需 Docker）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\package_submission.ps1
# 可选: -EntryId "17016457" -OutDir "submit"

param(
  [string]$EntryId = "17016457",
  [string]$OutDir = "submit"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Out = Join-Path $Root $OutDir
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$sourceZip = Join-Path $Out "${EntryId}源码.zip"
$workZip = Join-Path $Out "${EntryId}作品.zip"

$excludeDirNames = @(
  ".git", ".idea", ".cursor", "submit", "dist-submit",
  "agent-transcripts", "terminals", "__pycache__",
  "node_modules", "backups", "_tmp_standards", "_tmp_xlsx"
)
$excludeGlobs = @(
  "*.pyc", "*.pyo", "*.log",
  "*.tar.gz", "*.zip"
)

# 顶层打入内容（不含 docs / README / scripts）
$includeTopLevel = @(
  "frontend", "backend", ".venv",
  ".env.example",
  "公网访问说明.md",
  "部署说明书.md",
  "start.bat", "stop.bat",
  ".gitignore"
)

function Test-ExcludedRel {
  param([string]$Rel)
  $parts = $Rel -split "[\\/]"
  foreach ($p in $parts) {
    if ($excludeDirNames -contains $p) { return $true }
  }
  $name = $parts[-1]
  foreach ($g in $excludeGlobs) {
    if ($name -like $g) { return $true }
  }
  return $false
}

function Get-FilesToPack {
  $files = New-Object System.Collections.Generic.List[object]
  foreach ($top in $includeTopLevel) {
    $src = Join-Path $Root $top
    if (-not (Test-Path $src)) {
      Write-Warning "跳过不存在: $top"
      continue
    }
    if (Test-Path $src -PathType Leaf) {
      if (-not (Test-ExcludedRel -Rel $top)) {
        $files.Add([pscustomobject]@{ FullName = (Resolve-Path $src).Path; Rel = $top })
      }
      continue
    }
    Get-ChildItem -LiteralPath $src -Recurse -Force -File -ErrorAction SilentlyContinue | ForEach-Object {
      $rel = $_.FullName.Substring($Root.Length).TrimStart("\", "/")
      if (Test-ExcludedRel -Rel $rel) { return }
      $files.Add([pscustomobject]@{ FullName = $_.FullName; Rel = $rel })
    }
  }
  return $files
}

function New-ZipFromFileList {
  param(
    [System.Collections.IEnumerable]$Files,
    [string]$ZipPath
  )
  if (Test-Path $ZipPath) { Remove-Item -LiteralPath $ZipPath -Force }
  Add-Type -AssemblyName System.IO.Compression
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  $zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)
  try {
    $n = 0
    foreach ($f in $Files) {
      $entryName = ($f.Rel -replace "\\", "/")
      [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
        $zip,
        $f.FullName,
        $entryName,
        [System.IO.Compression.CompressionLevel]::Optimal
      )
      $n++
      if (($n % 2000) -eq 0) { Write-Host "  ... 已写入 $n 个文件" }
    }
    Write-Host "  共写入 $n 个文件"
  } finally {
    $zip.Dispose()
  }
}

# 打包前检查
$distIndex = Join-Path $Root "frontend\dist\index.html"
if (-not (Test-Path $distIndex)) {
  throw "缺少 frontend/dist/index.html，请先在 frontend 执行 npm run build"
}

Write-Host "==> 扫描待打包文件 ..."
$fileList = @(Get-FilesToPack)
Write-Host "  共 $($fileList.Count) 个文件"

Write-Host "==> 压缩源码包 ..."
New-ZipFromFileList -Files $fileList -ZipPath $sourceZip

Write-Host "==> 压缩作品包（同内容）..."
New-ZipFromFileList -Files $fileList -ZipPath $workZip

function Get-SizeMB([string]$p) {
  "{0:N1} MB" -f ((Get-Item $p).Length / 1MB)
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$z = [System.IO.Compression.ZipFile]::OpenRead($sourceZip)
try {
  $names = @($z.Entries | ForEach-Object { $_.FullName -replace "\\", "/" })
  $hasEnv = ($names | Where-Object { $_ -match '(^|/)backend/\.env$' }).Count -gt 0
  $hasDist = ($names | Where-Object { $_ -match '(^|/)frontend/dist/index\.html$' }).Count -gt 0
  $hasPublicMd = ($names | Where-Object { $_ -match '公网访问说明\.md$' }).Count -gt 0
  $hasNodeModules = ($names | Where-Object { $_ -match '(^|/)node_modules/' }).Count -gt 0
} finally { $z.Dispose() }

Write-Host ""
Write-Host "完成:"
Write-Host "  源码包:   $sourceZip  ($(Get-SizeMB $sourceZip))"
Write-Host "  作品包:   $workZip  ($(Get-SizeMB $workZip))"
Write-Host "  含 backend/.env: $hasEnv"
Write-Host "  含 frontend/dist: $hasDist"
Write-Host "  含 公网访问说明.md: $hasPublicMd"
Write-Host "  含 node_modules: $hasNodeModules (应为 False)"
Write-Host ""
Write-Host "注意: 压缩包内可能含真实 API Key，评委/组委会可见。"
