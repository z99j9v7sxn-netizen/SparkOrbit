# 备份 SparkOrbit：MySQL + uploads + static/media + chroma_data
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\backup_data.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\backup_data.ps1 -OutRoot "D:\backups" -MysqlBin "D:\mysql-8.1.0-winx64\bin"

param(
    [string]$OutRoot = "",
    [string]$MysqlBin = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$EnvFile = Join-Path $Backend ".env"

function Get-DatabaseUrl {
    if (Test-Path $EnvFile) {
        foreach ($line in Get-Content $EnvFile -Encoding UTF8) {
            $t = $line.Trim()
            if ($t -match '^\s*#' -or $t -eq "") { continue }
            if ($t -match '^DATABASE_URL=(.+)$') {
                return $Matches[1].Trim().Trim('"').Trim("'")
            }
        }
    }
    return "mysql+aiomysql://root:sparkorbit@127.0.0.1:3306/sparkorbit?charset=utf8mb4"
}

function Parse-MysqlUrl([string]$Url) {
    $cleaned = $Url -replace '^mysql\+aiomysql://', 'mysql://' -replace '^mysql\+pymysql://', 'mysql://'
    if ($cleaned -notmatch '^mysql://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?/([^?]+)') {
        throw "无法解析 DATABASE_URL: $Url"
    }
    return [pscustomobject]@{
        User     = [uri]::UnescapeDataString($Matches[1])
        Password = [uri]::UnescapeDataString($Matches[2])
        Host     = $Matches[3]
        Port     = if ($Matches[4]) { $Matches[4] } else { "3306" }
        Database = $Matches[5]
    }
}

function Resolve-MysqlDump {
    param([string]$BinDir)
    if ($BinDir) {
        $p = Join-Path $BinDir "mysqldump.exe"
        if (Test-Path $p) { return $p }
        throw "未找到 mysqldump: $p"
    }
    $cmd = Get-Command mysqldump -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($candidate in @(
            "D:\mysql-8.1.0-winx64\bin\mysqldump.exe",
            "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe",
            "C:\mysql\bin\mysqldump.exe"
        )) {
        if (Test-Path $candidate) { return $candidate }
    }
    throw "找不到 mysqldump，请用 -MysqlBin 指定 MySQL bin 目录"
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (-not $OutRoot) {
    $OutRoot = Join-Path $Root "backups"
}
$Dest = Join-Path $OutRoot "sparkorbit_$stamp"
$MysqlDir = Join-Path $Dest "mysql"
$UploadsDest = Join-Path $Dest "uploads"
$MediaDest = Join-Path $Dest "media"
$ChromaDest = Join-Path $Dest "chroma_data"

New-Item -ItemType Directory -Force -Path $MysqlDir, $UploadsDest, $MediaDest, $ChromaDest | Out-Null

$cfg = Parse-MysqlUrl (Get-DatabaseUrl)
$mysqldump = Resolve-MysqlDump -BinDir $MysqlBin
$sqlOut = Join-Path $MysqlDir "sparkorbit.sql"

Write-Host "Dumping MySQL $($cfg.Database) via $mysqldump ..."
$dumpArgs = @(
    "-h$($cfg.Host)",
    "-P$($cfg.Port)",
    "-u$($cfg.User)",
    "-p$($cfg.Password)",
    "--databases", $cfg.Database,
    "--default-character-set=utf8mb4",
    "--routines",
    "--triggers",
    "--single-transaction",
    "--result-file=$sqlOut"
)
& $mysqldump @dumpArgs
if ($LASTEXITCODE -ne 0) {
    throw "mysqldump 失败，exit=$LASTEXITCODE"
}

$uploadsSrc = Join-Path $Backend "uploads"
$mediaSrc = Join-Path $Backend "app\static\media"
$chromaSrc = Join-Path $Backend "chroma_data"

if (Test-Path $uploadsSrc) {
    Write-Host "Copying uploads ..."
    Copy-Item -Path (Join-Path $uploadsSrc "*") -Destination $UploadsDest -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path $mediaSrc) {
    Write-Host "Copying static/media ..."
    Copy-Item -Path (Join-Path $mediaSrc "*") -Destination $MediaDest -Recurse -Force -ErrorAction SilentlyContinue
}
if (Test-Path $chromaSrc) {
    Write-Host "Copying chroma_data ..."
    Copy-Item -Path (Join-Path $chromaSrc "*") -Destination $ChromaDest -Recurse -Force -ErrorAction SilentlyContinue
}

$manifest = @"
SparkOrbit backup
created: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
database: $($cfg.Host):$($cfg.Port)/$($cfg.Database)
mysql_dump: mysql/sparkorbit.sql
uploads: uploads/  (from backend/uploads)
media: media/      (from backend/app/static/media)
chroma: chroma_data/ (from backend/chroma_data)

Restore:
  1. mysql -uUSER -p < mysql/sparkorbit.sql
  2. copy uploads -> backend/uploads
  3. copy media -> backend/app/static/media
  4. copy chroma_data -> backend/chroma_data
  5. restart backend; optional: python scripts/verify_star_assets.py

Policy: MySQL holds metadata only; large videos/PDFs stay on disk (never BLOB).
"@
Set-Content -Path (Join-Path $Dest "MANIFEST.txt") -Value $manifest -Encoding UTF8

Write-Host "Backup complete: $Dest"
Get-ChildItem $Dest | Format-Table Name, Mode -AutoSize
