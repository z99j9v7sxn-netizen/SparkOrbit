"""路演 / Demo 上场前健康预检（管理端）。"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.llm import active_llm_provider, llm_available
from app.services.rag import onnx_model_ready, rag_available


async def build_demo_health(session: AsyncSession) -> dict[str, Any]:
    settings = get_settings()
    checks: list[dict[str, Any]] = []

    # LLM
    llm_ok = llm_available()
    checks.append(
        {
            "id": "llm",
            "label": "LLM Key",
            "ok": llm_ok,
            "detail": active_llm_provider() if llm_ok else "未配置 DeepSeek / 方舟 Key，将走模板降级",
        }
    )

    # RAG / ONNX
    rag_ok = rag_available()
    checks.append(
        {
            "id": "rag",
            "label": "RAG / ONNX",
            "ok": rag_ok,
            "detail": "可用" if rag_ok else ("ONNX 未就绪" if not onnx_model_ready() else "Chroma 不可用"),
        }
    )

    # DB
    db_ok = False
    db_detail = ""
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
        db_detail = "ok"
    except Exception as exc:  # noqa: BLE001
        db_detail = str(exc)[:160]
    checks.append({"id": "db", "label": "Database", "ok": db_ok, "detail": db_detail})

    # workers hint（无法可靠探测 uvicorn workers，给建议）
    checks.append(
        {
            "id": "workers",
            "label": "单 worker 建议",
            "ok": True,
            "detail": "资源 SSE 依赖进程内存；Demo 请用单 worker（uvicorn --workers 1）",
            "advisory": True,
        }
    )

    hard = [c for c in checks if not c.get("advisory")]
    overall = all(c["ok"] for c in hard)
    return {
        "ok": overall,
        "checks": checks,
        "tips": [
            "上场前确认 LLM Key 与 RAG 绿灯",
            "伴学点「生成资源」应打开资源工坊并出现 SSE",
            "管理端 /admin/agents 可回放 supervisor + workflow",
        ],
        "deepseek_configured": bool(settings.deepseek_api_key),
        "llm_provider": active_llm_provider(),
    }
