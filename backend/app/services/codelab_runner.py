"""代码舱执行：本地 subprocess 沙箱或 Docker sidecar HTTP。"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings

DEFAULT_TIMEOUT = 3


def run_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """在受限临时目录 subprocess 执行 Python；超时 kill。"""
    timeout = max(1, min(int(timeout), 10))
    with tempfile.TemporaryDirectory(prefix="codelab_") as tmp:
        script = Path(tmp) / "main.py"
        script.write_text(code, encoding="utf-8")
        try:
            proc = subprocess.run(
                ["python", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
            )
            return {
                "stdout": proc.stdout or "",
                "stderr": proc.stderr or "",
                "exit_code": proc.returncode,
                "runner": "subprocess",
            }
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            return {
                "stdout": stdout,
                "stderr": (stderr + "\n[timeout]").strip(),
                "exit_code": -1,
                "runner": "subprocess",
            }
        except FileNotFoundError:
            return {
                "stdout": "",
                "stderr": "python 解释器不可用",
                "exit_code": 127,
                "runner": "subprocess",
            }


def _run_remote(url: str, code: str, timeout: int) -> dict[str, Any]:
    endpoint = url.rstrip("/") + "/run"
    with httpx.Client(timeout=timeout + 2) as client:
        resp = client.post(endpoint, json={"code": code, "timeout": timeout})
        resp.raise_for_status()
        data = resp.json()
        data["runner"] = "docker-sidecar"
        return data


async def run_code(code: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """若配置 CODELAB_RUNNER_URL 则走 sidecar，否则本地 subprocess。"""
    if not (code or "").strip():
        return {"stdout": "", "stderr": "code is empty", "exit_code": 1, "runner": "none"}
    settings = get_settings()
    runner_url = (settings.codelab_runner_url or "").strip()
    timeout = max(1, min(int(timeout), 10))
    if runner_url:
        try:
            return _run_remote(runner_url, code, timeout)
        except Exception as exc:  # noqa: BLE001
            local = run_python(code, timeout=timeout)
            local["stderr"] = f"[sidecar failed: {exc}]\n{local.get('stderr', '')}".strip()
            return local
    return run_python(code, timeout=timeout)
