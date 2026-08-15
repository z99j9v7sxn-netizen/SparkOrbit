"""伴学 Supervisor 可调用的显式工具（薄封装现有服务，便于 AgentStep 落库与答辩口述）。"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

logger = logging.getLogger(__name__)


def action_result(
    *,
    type: str,
    label: str,
    status: str = "ok",
    error: str = "",
    tool_name: str = "",
    **payload: Any,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "type": type,
        "label": label,
        "status": status,
        "tool_name": tool_name or type,
    }
    if error:
        out["error"] = error
    out.update(payload)
    return out


async def tool_generate_learning_path(
    session: AsyncSession,
    user: User,
    *,
    goal: str,
) -> dict[str, Any]:
    """生成/刷新学习路径。"""
    from app.services.learning_path import generate_learning_path

    try:
        path = await generate_learning_path(session, user, goal=goal[:80] or "伴学推荐")
        return action_result(
            type="open_path",
            label="查看学习路径",
            tool_name="generate_learning_path",
            path_id=path.id,
            title=path.title,
            status="ok",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool_generate_learning_path failed")
        return action_result(
            type="open_path",
            label="生成路径失败，请稍后重试",
            tool_name="generate_learning_path",
            status="error",
            error=str(exc)[:200],
        )


def tool_start_resource_run(
    *,
    user_id: str,
    planet_slug: str,
    kinds: list[str],
    extra: str = "",
    quiz_types: Optional[list[str]] = None,
) -> dict[str, Any]:
    """登记并持久化资源生成任务（真正生成在 SSE consume 时 kickoff）。"""
    from app.services.resource_agents import register_resource_run

    if not planet_slug:
        return action_result(
            type="need_planet",
            label="请先选择一颗行星再生成资料",
            tool_name="start_resource_run",
            status="error",
            error="missing planet_slug",
        )
    run_id = f"res-{uuid.uuid4().hex[:10]}"
    try:
        register_resource_run(
            run_id,
            {
                "user_id": user_id,
                "planet_slug": planet_slug,
                "kinds": list(kinds),
                "extra": (extra or "")[:200],
                "quiz_types": list(quiz_types or []),
                "status": "registered",
                "source": "companion_supervisor",
            },
        )
        return action_result(
            type="stream_resources",
            label="开始生成学习资源",
            tool_name="start_resource_run",
            run_id=run_id,
            kinds=list(kinds),
            planet_slug=planet_slug,
            stream_hint=f"/api/resources/generate/{run_id}/stream",
            status="ok",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("tool_start_resource_run failed")
        return action_result(
            type="stream_resources",
            label="资源任务登记失败",
            tool_name="start_resource_run",
            status="error",
            error=str(exc)[:200],
        )


def tool_open_feynman(*, planet_slug: str = "") -> dict[str, Any]:
    return action_result(
        type="feynman",
        label="用费曼法讲解给我听",
        tool_name="open_feynman",
        planet_slug=planet_slug,
        status="ok",
    )


def tool_rag_search(topic: str, *, galaxy_slug: str = "", k: int = 3) -> dict[str, Any]:
    from app.services.rag import rag_available, retrieve_citations

    if not rag_available():
        return action_result(
            type="rag_search",
            label="知识检索不可用",
            tool_name="rag_search",
            status="degraded",
            error="RAG/ONNX unavailable",
            citations=[],
        )
    try:
        cites = retrieve_citations(topic, galaxy_slug=galaxy_slug or None, k=k)
        return action_result(
            type="rag_search",
            label=f"检索到 {len(cites)} 条依据",
            tool_name="rag_search",
            status="ok",
            citations=cites,
        )
    except Exception as exc:  # noqa: BLE001
        return action_result(
            type="rag_search",
            label="检索失败",
            tool_name="rag_search",
            status="error",
            error=str(exc)[:200],
            citations=[],
        )
