from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.api.challenge_routes import router as challenge_router
from app.api.exam_routes import router as exam_router
from app.api.review_routes import router as review_router
from app.api.vault_routes import router as vault_router
from app.api.ws import ws_router
from app.api.interview_routes import router as interview_router
from app.core.config import get_settings
from app.core.paths import MATERIALS_DIR, ensure_storage_dirs
from app.db.session import init_db
from app.middleware.maintenance import MaintenanceMiddleware
from app.models import (  # noqa: F401
    AiTaskRecord,
    Alert,
    ApiUsageLog,
    ChallengeQuestion,
    ChatMessage,
    ChatRoom,
    ChatRoomMember,
    ChatRoomMessage,
    ChatSession,
    Friendship,
    Galaxy,
    GatePolicy,
    HallucinationTicket,
    GeneratedResource,
    LearningPath,
    ProfileLearningEvent,
    Planet,
    PlanetMastery,
    ProfileExtraction,
    SchoolClass,
    SimulationEvent,
    SimulationRun,
    StarAsset,
    StudentProfile,
    StudentVault,
    StudyRoom,
    SystemSetting,
    User,
    VaultFile,
    VaultLink,
    WormholeMessage,
)
from app.models.zone_extras import FocusSession, MistakeRecord, RedeemRecord, WishLike, WishPost  # noqa: F401
from app.models.assignment import (  # noqa: F401
    Assignment,
    AssignmentSubmission,
    AttendanceRecord,
    TeacherBroadcast,
)
from app.models.mock_interview import InterviewReport, InterviewSession, InterviewTurn  # noqa: F401

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(MaintenanceMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    import logging
    import asyncio

    log = logging.getLogger("sparkorbit.startup")
    ensure_storage_dirs()
    log.info("init_db starting")
    await init_db()
    log.info("init_db done")
    # Chroma 本地 ONNX 预热（不阻塞过久；缺模型则跳过，禁止联网下载）
    try:
        from app.services import rag as rag_svc

        await asyncio.to_thread(rag_svc.warmup_chroma)
    except Exception as exc:  # noqa: BLE001
        log.warning("chroma warmup error: %s", exc)
    # 安全运营后台任务：告警扫描 + 每日安全日报 + 运行时配置缓存
    try:
        from app.services.ops_jobs import start_background_jobs

        start_background_jobs()
    except Exception as exc:  # noqa: BLE001
        log.warning("ops background jobs start error: %s", exc)


ensure_storage_dirs()
static_root = Path(__file__).resolve().parents[1]
media_root = Path(__file__).resolve().parent / "static" / "media"
media_root.mkdir(parents=True, exist_ok=True)
app.mount("/static/uploads", StaticFiles(directory=str(static_root / "uploads")), name="uploads")
app.mount("/static/assets", StaticFiles(directory=str(static_root / "assets")), name="assets")
app.mount("/static/media", StaticFiles(directory=str(media_root)), name="media")
# 项目根 资料/：课本与考研复习指导书 PDF（只读，避免拷贝进 uploads）
MATERIALS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/materials", StaticFiles(directory=str(MATERIALS_DIR)), name="materials")

app.include_router(router, prefix=settings.api_prefix)
app.include_router(challenge_router, prefix=settings.api_prefix)
app.include_router(exam_router, prefix=settings.api_prefix)
app.include_router(review_router, prefix=settings.api_prefix)
app.include_router(vault_router, prefix=settings.api_prefix)
app.include_router(interview_router, prefix=settings.api_prefix)
app.include_router(ws_router, prefix=settings.api_prefix)

# 本机无 Nginx 时：托管 frontend/dist，单进程提供 SPA + API
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _frontend_dist.is_dir() and (_frontend_dist / "index.html").is_file():
    _assets_dir = _frontend_dist / "assets"
    if _assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="frontend_assets")

    @app.get("/")
    async def spa_index() -> FileResponse:
        return FileResponse(_frontend_dist / "index.html")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        # 已由上方 mount / include_router 处理的路径不会落到这里
        candidate = (_frontend_dist / full_path).resolve()
        try:
            candidate.relative_to(_frontend_dist.resolve())
        except ValueError:
            return FileResponse(_frontend_dist / "index.html")
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_frontend_dist / "index.html")
