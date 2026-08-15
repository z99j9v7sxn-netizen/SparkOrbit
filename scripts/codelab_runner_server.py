#!/usr/bin/env python3
"""CodeLab sidecar：在容器内受限 subprocess 执行 Python（MVP HTTP 8091）。

生产环境应由 Docker 隔离；本脚本供 docker-compose `codelab-runner` 服务使用。
compose 侧配置 mem_limit/cpus/pids_limit/read_only；本服务仅内网 expose，无公网出站依赖；
超时由 execute_python 强制（默认 3s，上限 10s）。
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST = "0.0.0.0"
PORT = 8091
MAX_CODE_LEN = 20000
DEFAULT_TIMEOUT = 3


def execute_python(code: str, timeout: int = DEFAULT_TIMEOUT) -> dict:
    timeout = max(1, min(int(timeout), 10))
    with tempfile.TemporaryDirectory(prefix="codelab_sidecar_") as tmp:
        script = Path(tmp) / "main.py"
        script.write_text(code[:MAX_CODE_LEN], encoding="utf-8")
        try:
            proc = subprocess.run(
                ["python", str(script)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
            )
            return {"stdout": proc.stdout or "", "stderr": proc.stderr or "", "exit_code": proc.returncode}
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode("utf-8", errors="replace") if exc.stdout else ""
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            return {"stdout": stdout, "stderr": (stderr + "\n[timeout]").strip(), "exit_code": -1}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/") in ("", "/health"):
            self._json(200, {"ok": True, "service": "codelab-runner"})
            return
        self._json(404, {"ok": False, "detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path.rstrip("/") != "/run":
            self._json(404, {"ok": False, "detail": "POST /run only"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"ok": False, "detail": "invalid json"})
            return
        code = str(data.get("code") or "")
        timeout = int(data.get("timeout") or DEFAULT_TIMEOUT)
        if not code.strip():
            self._json(400, {"ok": False, "detail": "code is empty"})
            return
        result = execute_python(code, timeout=timeout)
        result["ok"] = True
        self._json(200, result)


def main() -> None:
    server = HTTPServer((HOST, PORT), Handler)
    print(f"codelab-runner listening on {HOST}:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
