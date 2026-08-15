#!/usr/bin/env python3
"""把 Better Harness CLI / 本地产物规范成 AdminHarness 字段形状。"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "evidence" / "better-harness"
FINDINGS = OUT / "findings.json"


def normalize(data: dict) -> dict:
    out = dict(data)
    out.setdefault("status", "ok")
    out.setdefault("project", "SparkOrbit")
    raw = out.get("findings") or []
    if not isinstance(raw, list):
        raw = []
    items = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        cause = str(item.get("cause") or item.get("summary") or item.get("description") or "")
        expected = str(item.get("expected") or item.get("expectation") or item.get("should") or "")
        repair = str(item.get("repair") or item.get("fix") or item.get("action") or "")
        items.append(
            {
                **item,
                "id": str(item.get("id") or f"finding-{i + 1}"),
                "priority": str(item.get("priority") or "medium"),
                "dimension": str(
                    item.get("dimension") or item.get("dim") or item.get("category") or "evidence"
                ),
                "title": str(item.get("title") or item.get("name") or f"发现 {i + 1}"),
                "cause": cause,
                "expected": expected or "见仓库约定 / AGENTS.md",
                "repair": repair or "按 Cause 补齐后重跑 Harness",
                "summary": str(item.get("summary") or cause),
            }
        )
    out["findings"] = items
    if not isinstance(out.get("dimensions"), list):
        out["dimensions"] = []
    return out


def main() -> None:
    if not FINDINGS.is_file():
        print(f"skip: {FINDINGS} missing")
        return
    data = json.loads(FINDINGS.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("skip: findings.json is not an object")
        return
    FINDINGS.write_text(json.dumps(normalize(data), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"normalized {FINDINGS}")


if __name__ == "__main__":
    main()
