"""Probe 讯飞数字人视频：创建短任务并查询若干次，打印原始 header。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import xf_digital_human as xf  # noqa: E402


async def main() -> None:
    print("available:", xf.xf_digital_human_available())
    app_id, key, secret = xf._creds()
    print("app_id:", app_id[:4] + "***" if app_id else "(empty)")
    print("api_key set:", bool(key), "api_secret set:", bool(secret))
    print("host:", xf._host())
    tid = await xf.create_task("用五十个字介绍IP地址与子网掩码。", word_count=50)
    print("created task_id:", tid)
    for i in range(12):
        r = await xf.query_task(tid)
        header = (r.get("raw") or {}).get("header") or {}
        print(
            f"poll[{i}]",
            json.dumps(
                {
                    "task_status": r.get("status"),
                    "code": r.get("code"),
                    "message": r.get("message"),
                    "done": r.get("done"),
                    "has_video": bool(r.get("video_url")),
                    "payload_keys": list((r.get("payload") or {}).keys()),
                    "header_keys": list(header.keys()),
                },
                ensure_ascii=False,
            ),
        )
        if r.get("done") or (str(r.get("status") or "") in {"3", "4"} and r.get("video_url")):
            print("DONE video=", r.get("video_url"))
            break
        await asyncio.sleep(8)


if __name__ == "__main__":
    asyncio.run(main())
