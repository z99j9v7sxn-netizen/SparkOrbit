@echo off
setlocal
cd /d "%~dp0"

echo [停止] 结束占用 8000 端口的 SparkOrbit 进程...
set "_killed=0"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
  taskkill /F /PID %%P >nul 2>&1
  if not errorlevel 1 set "_killed=1"
  echo   已结束 PID=%%P
)

if "%_killed%"=="0" (
  echo 未发现监听 8000 的进程（可能已停止）。
) else (
  echo 已停止。
)
echo.
pause
endlocal
