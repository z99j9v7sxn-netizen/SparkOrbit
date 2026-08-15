"""教学分镜溯源校验：Seedance 硬门槛。"""
from __future__ import annotations

from typing import Any


def _candidate_pages(citations: list[dict]) -> set[tuple[str, int]]:
    pages: set[tuple[str, int]] = set()
    for c in citations or []:
        if not isinstance(c, dict):
            continue
        book = str(c.get("book") or c.get("book_title") or c.get("source") or "").strip()
        page = c.get("page") or c.get("page_no") or 0
        try:
            page_no = int(page)
        except (TypeError, ValueError):
            page_no = 0
        if book and page_no > 0:
            pages.add((book, page_no))
    return pages


def validate_slides_provenance(slides: list[dict], citations: list[dict]) -> dict[str, Any]:
    """校验每幕分镜是否具备可核验的 source_pages。"""
    candidate = _candidate_pages(citations)
    issues: list[str] = []
    mismatched = 0
    checked = 0
    if not slides:
        return {
            "ok": False,
            "issues": ["无分镜"],
            "slide_count": 0,
            "conflict_ratio": 1.0,
            "citation_pages": 0,
        }

    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            issues.append(f"slide[{i}] 非对象")
            mismatched += 1
            checked += 1
            continue
        src_pages = slide.get("source_pages")
        if not isinstance(src_pages, list) or not src_pages:
            issues.append(f"slide[{i}] 缺少 source_pages")
            mismatched += 1
            checked += 1
            continue
        valid_ref = False
        slide_conflict = False
        for ref in src_pages:
            if not isinstance(ref, dict):
                continue
            book = str(ref.get("book") or ref.get("book_title") or "").strip()
            page = ref.get("page") or ref.get("page_no") or 0
            try:
                page_no = int(page)
            except (TypeError, ValueError):
                page_no = 0
            if not book or page_no <= 0:
                continue
            checked += 1
            if candidate and (book, page_no) not in candidate:
                issues.append(f"slide[{i}] 页码 {book} p.{page_no} 不在引用候选集")
                slide_conflict = True
                mismatched += 1
                continue
            valid_ref = True
        if not valid_ref:
            if not issues or not any(f"slide[{i}]" in x for x in issues):
                issues.append(f"slide[{i}] source_pages 无效")
            if not slide_conflict:
                mismatched += 1
                checked += 1

    conflict_ratio = (mismatched / checked) if checked else (1.0 if issues else 0.0)
    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "slide_count": len(slides),
        "citation_pages": len(candidate),
        "conflict_ratio": round(conflict_ratio, 3),
        "mismatched": mismatched,
        "checked": checked,
    }
