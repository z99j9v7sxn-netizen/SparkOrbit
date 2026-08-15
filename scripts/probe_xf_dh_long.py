"""长时间探针：观察讯飞数字人 task_status 是否从 1/2 变为 3/4。"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services import xf_digital_human as xf  # noqa: E402


async def main() -> None:
    # 清掉可能缓存的 settings
    get_settings.cache_clear()
    s = get_settings()
    print("XF_DH_APP_ID:", (s.xf_dh_app_id or s.xf_app_id)[:6] + "***")
    print("word_count:", s.xf_dh_word_count, "timeout:", s.xf_dh_timeout)
    tid = await xf.create_task("用八十个字讲解IP地址与子网掩码的基本概念。", word_count=80)
    print("created:", tid)
    for i in range(24):  # ~2 分钟
        r = await xf.query_task(tid)
        st = r.get("status")
        print(
            f"t={(i+1)*5:3d}s status={st} code={r.get('code')} "
            f"payload={list((r.get('payload') or {}).keys())} msg={r.get('message')}"
        )
        if st in {"3", "4"} or r.get("done"):
            print("SUCCESS raw header:", json.dumps((r.get("raw") or {}).get("header"), ensure_ascii=False))
            if r.get("payload"):
                print("payload keys:", list(r["payload"].keys()))
                print("video:", (r["payload"].get("video") or r["payload"].get("video_url") or "")[:120])
            return
        await asyncio.sleep(5)
    print("STILL PENDING after ~2min — XF queue not advancing (not a local auth bug).")


if __name__ == "__main__":
    asyncio.run(main())
