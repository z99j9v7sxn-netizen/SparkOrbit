from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.db.session import AsyncSessionLocal
from app.services.admin import is_maintenance_enabled


class MaintenanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api"):
            return await call_next(request)
        if (
            path in {"/api/health", "/api/system/status"}
            or path.startswith("/api/admin")
            or path.startswith("/api/auth/")
        ):
            return await call_next(request)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ").strip()
            from app.core.security import resolve_user_id_from_token

            user_id = resolve_user_id_from_token(token)
            if user_id:
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select

                    from app.models.user import User

                    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
                    if user and user.role == "admin":
                        return await call_next(request)

        async with AsyncSessionLocal() as session:
            enabled, message = await is_maintenance_enabled(session)
        if enabled:
            return JSONResponse(status_code=503, content={"detail": message})
        return await call_next(request)
