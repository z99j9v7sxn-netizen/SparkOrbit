"""本机 Obsidian Vault ↔ SparkOrbit 云端增量同步 Agent。

用法：
  1. 在本机解压「导出 Vault」到某目录，并用 Obsidian 打开
  2. 设置环境变量后运行：

  set SPARKORBIT_TOKEN=你的登录JWT
  set SPARKORBIT_API=http://127.0.0.1:8000
  set SPARKORBIT_VAULT=C:\\path\\to\\SparkOrbit-student001
  .\\.venv\\Scripts\\python.exe scripts\\obsidian_sync_agent.py

默认每 8 秒双向同步一次（先 pull 云端新文件，再 push 本机变更）。
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


API = env("SPARKORBIT_API", "http://127.0.0.1:8000").rstrip("/")
TOKEN = env("SPARKORBIT_TOKEN")
VAULT = Path(env("SPARKORBIT_VAULT") or "")
INTERVAL = float(env("SPARKORBIT_SYNC_INTERVAL", "8") or "8")


def req(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    r = urllib.request.Request(f"{API}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_manifest(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if ".obsidian" in p.parts and p.name not in ("app.json",):
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        try:
            out[rel] = file_hash(p)
        except OSError:
            pass
    return out


def write_local(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    if not TOKEN:
        print("FAIL: set SPARKORBIT_TOKEN")
        return 1
    if not VAULT.exists():
        print(f"FAIL: vault dir not found: {VAULT}")
        return 1
    print(f"sync {VAULT} <-> {API} every {INTERVAL}s")
    while True:
        try:
            remote = req("GET", "/api/vault/sync/manifest")
            remote_map = {f["path"]: f["hash"] for f in remote.get("files") or []}
            local_map = local_manifest(VAULT)

            # pull: remote newer / missing locally
            to_pull = [p for p, h in remote_map.items() if local_map.get(p) != h]
            if to_pull:
                pulled = req("POST", "/api/vault/sync/pull", {"paths": to_pull})
                for item in pulled.get("files") or []:
                    write_local(VAULT, item["path"], item.get("content") or "")
                print(f"pull {len(pulled.get('files') or [])} files (rev={pulled.get('revision')})")

            # push: local different
            local_map = local_manifest(VAULT)
            to_push = []
            for p, h in local_map.items():
                if remote_map.get(p) == h:
                    continue
                fp = VAULT / p
                if not fp.exists():
                    continue
                try:
                    content = fp.read_text(encoding="utf-8")
                except OSError:
                    continue
                to_push.append({"path": p, "content": content})
            if to_push:
                pushed = req("POST", "/api/vault/sync/push", {"files": to_push})
                print(f"push {pushed.get('written')} files (rev={pushed.get('revision')})")
            if not to_pull and not to_push:
                print("ok idle", flush=True)
        except urllib.error.HTTPError as exc:
            print(f"HTTP {exc.code}: {exc.read()[:200]!r}")
        except Exception as exc:
            print(f"ERR {exc}")
        time.sleep(max(3.0, INTERVAL))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("stopped")
        raise SystemExit(0)
