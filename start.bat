@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ========================================
echo  SparkOrbit 本机启动（无需 Docker）
echo  推荐优先访问公网: https://wikj.online
echo  说明见: 公网访问说明.md
echo ========================================
echo.

if not exist "frontend\dist\index.html" (
  echo [错误] 未找到 frontend\dist\index.html
  echo 请使用完整提交包，或在 frontend 目录执行 npm run build。
  pause
  exit /b 1
)

set "PY="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.12 -c "import sys" >nul 2>&1
  if not errorlevel 1 set "PY=py -3.12"
  if not defined PY (
    py -3.11 -c "import sys" >nul 2>&1
    if not errorlevel 1 set "PY=py -3.11"
  )
  if not defined PY (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=py -3"
  )
)
if not defined PY (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
    if not errorlevel 1 set "PY=python"
  )
)

if not defined PY (
  echo [错误] 未检测到 Python 3.11+。
  echo 请安装 Python 3.12 并勾选 Add to PATH：
  echo   https://www.python.org/downloads/
  echo.
  echo 也可直接打开公网验收（无需本机安装）:
  echo   https://wikj.online
  pause
  exit /b 1
)

echo [检测] 使用解释器: %PY%

if not exist ".venv\Scripts\python.exe" (
  echo [准备] 创建虚拟环境 .venv ...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo [错误] 创建虚拟环境失败。
    pause
    exit /b 1
  )
)

set "VENV_PY=%CD%\.venv\Scripts\python.exe"
"%VENV_PY%" -c "import fastapi,uvicorn,aiosqlite" >nul 2>&1
if errorlevel 1 (
  echo [准备] 安装依赖（首次可能需数分钟）...
  "%VENV_PY%" -m pip install -U pip
  "%VENV_PY%" -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络后重试。
    pause
    exit /b 1
  )
)

if not exist "backend\.env" (
  if exist "backend\.env.example" (
    copy /Y "backend\.env.example" "backend\.env" >nul
    echo [提示] 已从 backend\.env.example 创建 backend\.env
  )
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
  echo [提示] 结束占用 8000 端口的进程 PID=%%P
  taskkill /F /PID %%P >nul 2>&1
)

echo [启动] 后端 + 前端静态资源  http://127.0.0.1:8000
REM 写入临时启动脚本，避免 start/cmd 嵌套引号问题；强制 SQLite
(
  echo @echo off
  echo cd /d "%CD%\backend"
  echo set DATABASE_URL=sqlite+aiosqlite:///./sparkorbit.db
  echo set SPARKORBIT_CHROMA_OFFLINE=1
  echo "%VENV_PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
  echo if errorlevel 1 pause
) > "%TEMP%\sparkorbit_run.bat"
start "SparkOrbit" cmd /k "%TEMP%\sparkorbit_run.bat"

echo [等待] 服务就绪...
set /a _tries=0
:wait_loop
set /a _tries+=1
if %_tries% GTR 90 goto wait_done
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/health -TimeoutSec 2).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto wait_loop

:wait_done
start "" "http://127.0.0.1:8000"

echo.
echo ========================================
echo  SparkOrbit 已启动
echo  本机: http://127.0.0.1:8000
echo  公网（推荐）: https://wikj.online
echo  演示账号: student001 / teacher001 / admin001
echo  密码: 123456
echo  停止: 双击 stop.bat 或关闭 SparkOrbit 窗口
echo ========================================
echo.
pause
endlocal
