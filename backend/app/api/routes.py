from __future__ import annotations

import asyncio
import json
import logging
import uuid

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.paths import NOTES_DIR, RESOURCES_DIR, TREEHOLE_DIR
from app.core.security import create_access_token
from app.db.session import get_db
from app.dependencies import require_admin, require_current_user, require_teacher, require_teacher_or_admin
from app.schemas.admin import (
    AgentRunOut,
    ApiErrorItem,
    ApiQuotaOut,
    ApiUsageSummary,
    GalaxyBrief,
    GalaxyUpsertRequest,
    ImportStudentsRequest,
    ImportStudentsResponse,
    MaintenanceOut,
    MaintenanceUpdateRequest,
    PlanetBrief,
    PlanetUpsertRequest,
    SystemOverviewOut,
    UserAdminItem,
    UserAdminUpdateRequest,
)
from app.schemas.avatar import AvatarGenerateResponse
from app.schemas.account import ClassBrief, RegisterResponse, TeacherBrief
from app.schemas.ai_tutor import GradeRequest, GradeResponse, SimilarQuestionsRequest, SimilarQuestionsResponse
from app.schemas.auth import (
    CheckUsernameRequest,
    CheckUsernameResponse,
    LoginRequest,
    LoginResponse,
    PreflightRequest,
    PreflightResponse,
    UserInfo,
    UserUpdateRequest,
)
from app.schemas.chat import ChatMessageCreate, ChatMessageOut, ChatSessionCreate, ChatSessionOut
from app.schemas.chat_room import (
    ChatReactionIn,
    ChatReactionOut,
    ChatRoomMessageOut,
    ChatRoomOut,
    ChatSendRequest,
    ChatSummaryOut,
    GroupChatCreateIn,
    GroupInviteIn,
    PrivateChatCreateRequest,
    TopicRoomCreateIn,
)
from app.schemas.extras import (
    AiQuizOut,
    AiQuizSubmitOut,
    AiQuizSubmitRequest,
    FocusYearlyOut,
    KnowledgeAskIn,
    KnowledgeAskOut,
    KnowledgeExplainOut,
    MoodDiaryIn,
    MoodDiaryOut,
    NotificationOut,
    OralPracticeIn,
    OralPracticeOut,
    TreeHoleCommentIn,
    TreeHoleCommentOut,
    TreeHolePostIn,
    TreeHolePostOut,
    TreeHoleReactIn,
    TtsRequest,
)
from app.schemas.note import (
    LessonResourceOut,
    LessonResourceTextIn,
    NoteIn,
    NoteOut,
    NoteUpdateIn,
    PromoteResourceIn,
)
from app.schemas.pet import PetAffinityIn, PetAffinityOut, PetManifestOut, PetSelectRequest
from app.schemas.profile_history import ProfileHistoryItem
from app.schemas.study import OccupantOut, StudyConstellationOut, StudyJoinResponse, StudyRoomOut
from app.schemas.zone_extras import (
    AchievementOut,
    BuddyMatchOut,
    DailyTaskOut,
    DailyTaskToggleIn,
    EquippedTitleIn,
    FocusHeatmapOut,
    FocusLeaderboardItem,
    FocusSessionIn,
    FocusSummaryOut,
    GameChallengeIn,
    GameChallengeOut,
    KnowledgeGraphOut,
    LeisureSessionIn,
    LeisureSessionOut,
    MilestoneOut,
    MistakeIn,
    MistakeOut,
    OwnedShopItemOut,
    ProgressBoardOut,
    RedeemIn,
    ShopItemOut,
    SignInOut,
    StudyStreakOut,
    StudyThemeIn,
    ForumPostIn,
    ForumPostOut,
    ForumPromoteIn,
    ForumPromoteOut,
    WishIn,
    WishOut,
)
from app.schemas.galaxy import (
    AddFriendRequest,
    AssessmentStartOut,
    AssessmentSubmitOut,
    AssessmentSubmitRequest,
    AvatarStateOut,
    ChallengeOut,
    CompanionChatRequest,
    CompanionChatResponse,
    ConstellationOut,
    FriendItem,
    FragmentProgress,
    GalaxyDetailOut,
    GalaxyOut,
    LeaderboardItem,
    LessonPlanOut,
    MasteryOverviewOut,
    MasteryTrendOut,
    OrbitSnapshotOut,
    ReviewPlanetRequest,
    ReviewPlanetResult,
    SosEmitRequest,
    SosRespondRequest,
    StudentAlertOut,
    SubmitChallengeRequest,
    SubmitChallengeResult,
    WeeklyActivityOut,
    WormholeMessageOut,
    WormholeSendRequest,
)
from app.schemas.resource_gen import (
    EvaluationReportOut,
    GeneratedResourceOut,
    LearningPathGenerateRequest,
    LearningPathOut,
    PathMountRequest,
    ProfileTimelineItem,
    RecommendationItem,
    ResourceGenerateRequest,
    ResourceGenerateResponse,
)
from app.schemas.simulation import MirrorSimulationRequest, MirrorSimulationResponse
from app.schemas.student_profile import ProfileRequest, ProfileResponse, StudentProfileExtract
from app.schemas.assignment import (
    AssignmentCreateIn,
    AssignmentExtractOut,
    AssignmentOut,
    AssignmentSubmitIn,
    AttendanceRow,
    AttendanceSetIn,
    BroadcastIn,
    BroadcastOut,
    GradebookRow,
    GradeSubmissionIn,
    SubmissionOut,
)
from app.schemas.teacher import (
    ClassBriefOut,
    ClassOverviewOut,
    DispatchTaskRequest,
    DispatchTaskResponse,
    ReviewScanOut,
    ReviewScanRequest,
    GatePolicyOut,
    GatePolicyUpdate,
    GravityWellItem,
    InterventionRequest,
    InterventionResponse,
    ProfileMatrixOut,
    StudentRiskItem,
)
from app.schemas.teacher_suite import (
    CalendarEventIn,
    DirectMessageSendIn,
    GroupDispatchIn,
    GroupIn,
    GroupUpdateIn,
    MistakeDispatchIn,
    PraiseIn,
    QuestionAiGenerateIn,
    QuestionBulkIn,
    QuestionImportAssignmentIn,
    QuestionIn,
    QuestionUpdateIn,
    ResourceRecommendIn,
    ResourceReviewIn,
)
from app.services import admin as admin_service
from app.services import social as social_service
from app.services import teacher as teacher_service
from app.services import teacher_extras as teacher_extras_service
from app.services import teacher_suite as teacher_suite_service
from app.services.assessment import start_assessment, submit_answer as submit_assessment_answer
from app.services.account import (
    link_demo_student,
    list_classes,
    list_teachers,
    register_user,
    seed_classes,
    update_user_profile,
)
from app.services.ai_tutor import generate_similar_questions, grade_answers
from app.services.auth import (
    authenticate_user,
    check_username_available,
    preflight_username_role,
    role_mismatch_message,
    seed_demo_users,
)
from app.services.chat_service import (
    create_group_room,
    create_private_room,
    create_topic_room,
    delete_topic_room,
    ensure_class_room_for_student,
    invite_to_group,
    list_classmates,
    list_room_messages,
    list_user_rooms,
    send_room_message,
    summarize_room_today,
    toggle_message_reaction,
    user_avatar_url,
)
from app.services.notification_service import list_notifications, mark_all_read, mark_read, unread_count
from app.services.note_service import (
    create_lesson_resource,
    create_lesson_resource_from_text,
    create_note,
    delete_lesson_resource,
    delete_note,
    list_lesson_resources,
    list_notes,
    promote_generated_to_starlib,
    promote_lesson_resource_to_starlib,
    update_note,
)
from app.services.tree_hole_service import (
    create_comment,
    create_diary,
    create_post,
    delete_post,
    list_comments,
    list_diaries,
    list_posts,
    react_post,
    toggle_like,
)
from app.services.upload_service import save_upload_file
from app.services.pet_service import affinity_level, bump_pet_affinity, list_pet_manifests, list_owned_pet_slugs, set_equipped_title, set_study_theme, set_user_pet
from app.services.study_service import (
    get_user_study_room,
    join_room as study_join_room,
    leave_room as study_leave_room,
    list_constellations as study_list_constellations,
    list_occupants as study_list_occupants,
    list_rooms as study_list_rooms,
    list_teacher_study_presence,
    seed_study_rooms,
    update_occupant_status,
)
from app.services.resource_forum import create_post as create_forum_post
from app.services.resource_forum import like_post as like_forum_post
from app.services.resource_forum import list_posts as list_forum_posts
from app.services.resource_forum import promote_to_starlib as promote_forum_post
from app.services.zone_extras import (
    add_mistake,
    ask_knowledge,
    buddy_matches,
    create_focus_session,
    create_game_challenge,
    create_wish,
    delete_mistake,
    ensure_daily_tasks,
    explain_knowledge_node,
    fetch_sign_in_status,
    focus_heatmap,
    focus_leaderboard,
    focus_summary,
    focus_yearly_calendar,
    generate_ai_quiz,
    knowledge_graph,
    like_wish,
    list_achievements,
    list_milestones,
    list_mistakes,
    list_pending_challenges,
    list_shop_items,
    list_shop_owned,
    list_wishes,
    ocr_mistake_from_image,
    progress_board,
    record_leisure_session,
    redeem_item,
    respond_game_challenge,
    submit_ai_quiz,
    sign_in_today,
    study_streak_calendar,
    toggle_daily_task,
)
from app.services.user_info import user_to_info
from app.services.challenge import generate_challenge, submit_challenge
from app.services.companion import companion_chat, companion_chat_stream
from app.services.companion_supervisor import run_companion_supervisor
from app.services.constellation import list_constellations
from app.services.fragments import get_fragment_progress
from app.services.galaxy_forge import forge_galaxy_from_pdf
from app.services.galaxy_service import (
    get_avatar_state,
    get_galaxy_detail,
    get_mastery_overview,
    get_orbit_snapshot,
    get_planet_mastery_trend,
    get_weekly_activity,
    list_galaxies,
    list_student_alerts,
)
from app.services.memory_decay import review_planet
from app.services.evaluation import build_evaluation_report, evaluation_suggestions_for_path
from app.services.learning_path import (
    build_recommendations,
    complete_path_step,
    generate_learning_path,
    get_active_path,
    mount_path_step,
    sync_remediation_steps_to_path,
)
from app.services.profile_refresh import list_profile_timeline, record_learning_event, refresh_profile_from_events
from app.services.profiles import get_latest_profile, get_profile_by_id, list_profile_history, save_student_profile
from app.services.improvement import (
    create_remediation_plan,
    get_user_profile_meta,
    list_pending_for_teacher,
    list_user_plans,
    override_improvement,
    submit_improvement,
    update_plan_step,
)
from app.schemas.improvement import ImprovementOverrideRequest, ImprovementSubmitRequest, PlanStepUpdate, ProfileMetaOut
from app.models.simulation import SimulationEvent as SimulationEventRow, SimulationRun
from app.services.resource_agents import (
    format_resource_sse,
    get_resource,
    get_resource_run,
    list_user_resources,
    register_resource_run,
    run_resource_generation,
)
from app.services.profiling import extract_student_profile
from app.services.seed_content import seed_content
from app.services.avatar_service import generate_avatar
from app.services.simulation import (
    format_sse,
    get_run,
    register_run,
    run_mirror_simulation,
    run_multiverse_simulation,
)
from app.services.sos import emit_sos, list_sos, respond_sos

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get('/health')
async def health_check() -> dict[str, str | bool]:
    from app.services.llm import llm_available
    from app.services.xf_digital_human import xf_digital_human_available

    settings = get_settings()
    vms_ok = bool(
        (settings.xf_vms_app_id or "").strip()
        and (settings.xf_vms_api_key or "").strip()
        and (settings.xf_vms_api_secret or "").strip()
        and (settings.xf_vms_scene_id or "").strip()
    )
    return {
        'status': 'ok',
        'service': 'SparkOrbit 星轨学图',
        'llm_configured': llm_available(),
        'llm_model': get_settings().deepseek_model,
        'xf_digital_human': xf_digital_human_available(),
        'xf_vms_avatar': vms_ok,
    }


@router.get('/public/health-capabilities')
async def health_capabilities() -> dict:
    """外部可扩展能力清单（附加分：可扩展 API）。"""
    from app.services.ark_vision import ark_vision_available
    from app.services.llm import llm_available, llm_status
    from app.services.seedance_service import seedance_available
    from app.services.xf_digital_human import xf_digital_human_available

    settings = get_settings()
    langgraph_ok = False
    try:
        import langgraph  # noqa: F401

        langgraph_ok = True
    except Exception:  # noqa: BLE001
        langgraph_ok = False

    status_llm = llm_status()
    return {
        'status': 'ok',
        'agents': {
            'resource': ['DocAgent', 'MindAgent', 'QuizAgent', 'ReadAgent', 'MediaAgent', 'DeckAgent', 'CodeAgent'],
            'simulation': ['Teacher', 'Mirror', 'Evaluator', 'PathPlanner'],
            'tutor_modes': ['companion', 'tutor_socratic', 'feynman', 'supervisor'],
        },
        'llm': {
            'configured': llm_available(),
            'provider': status_llm.get('provider'),
            'label': status_llm.get('label'),
            'model': status_llm.get('model') or settings.deepseek_model,
            'deepseek': status_llm.get('deepseek'),
            'doubao': status_llm.get('doubao'),
        },
        'seedance': {
            'configured': seedance_available(),
            'endpoint': settings.ark_seedance_model,
            'foundation_model': settings.ark_seedance_foundation_model,
            'base_url': settings.ark_base_url,
        },
        'ark_vision': {
            'configured': ark_vision_available(),
            'endpoint': settings.ark_vision_model,
            'foundation_model': settings.ark_vision_foundation_model,
            'base_url': settings.ark_base_url,
        },
        'quality_scoring': True,
        'hallucination_guard': True,
        'evaluation_to_path': True,
        'langgraph': langgraph_ok,
        'xf_speech': bool(settings.xf_app_id and settings.xf_api_key and settings.xf_api_secret),
        'xf_tts': bool(settings.xf_app_id and settings.xf_api_key and settings.xf_api_secret),
        'xf_digital_human': xf_digital_human_available(),
        'xf_vms_avatar': bool(
            (settings.xf_vms_app_id or '').strip()
            and (settings.xf_vms_api_key or '').strip()
            and (settings.xf_vms_api_secret or '').strip()
            and (settings.xf_vms_scene_id or '').strip()
        ),
    }


@router.on_event('startup')
async def bootstrap() -> None:
    """演示数据 / RAG 灌库放到后台，避免 Chroma 下模型阻塞导致健康检查失败。"""
    import asyncio
    import logging

    log = logging.getLogger('sparkorbit.bootstrap')

    async def _run() -> None:
        try:
            async for db in get_db():
                await seed_demo_users(db)
                await seed_content(db)
                await seed_classes(db)
                await seed_study_rooms(db)
                await link_demo_student(db)
                break
            log.info('bootstrap seed finished')
        except Exception:
            log.exception('bootstrap seed failed')

    asyncio.create_task(_run())


# ----------------------------- 鉴权 -----------------------------
@router.post('/auth/preflight', response_model=PreflightResponse)
async def auth_preflight(request: PreflightRequest, db: AsyncSession = Depends(get_db)) -> PreflightResponse:
    ok, message = await preflight_username_role(db, request.username, request.role)
    return PreflightResponse(ok=ok, message=message)


@router.post('/auth/check-username', response_model=CheckUsernameResponse)
async def auth_check_username(
    request: CheckUsernameRequest, db: AsyncSession = Depends(get_db)
) -> CheckUsernameResponse:
    available, message = await check_username_available(db, request.username)
    return CheckUsernameResponse(available=available, message=message)


@router.post('/auth/login', response_model=LoginResponse)
async def login(
    request: LoginRequest, http_request: Request, db: AsyncSession = Depends(get_db)
) -> LoginResponse:
    from app.services.audit import record_login

    user = await authenticate_user(db, request.username, request.password)
    if user is None:
        await record_login(
            db,
            user_id='',
            username=request.username,
            success=False,
            reason='用户名或密码错误',
            request=http_request,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='用户名或密码错误')
    if user.role != (request.role or '').strip():
        await record_login(
            db,
            user_id=user.id,
            username=user.username,
            success=False,
            reason='角色不匹配',
            request=http_request,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=role_mismatch_message(request.role, user.role),
        )
    await record_login(
        db, user_id=user.id, username=user.username, success=True, request=http_request
    )
    return LoginResponse(
        access_token=create_access_token(user_id=user.id, role=user.role),
        user=user_to_info(user),
    )


@router.post('/auth/register', response_model=RegisterResponse)
async def register(
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(default=""),
    role: str = Form(default="student"),
    teacher_id: str = Form(default=""),
    class_id: str = Form(default=""),
    description: str = Form(default=""),
    photo: UploadFile | None = File(default=None),
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    try:
        user = await register_user(
            db,
            username=username,
            password=password,
            display_name=display_name,
            role=role,
            teacher_id=teacher_id,
            class_id=class_id,
            description=description,
            photo=photo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RegisterResponse(
        access_token=create_access_token(user_id=user.id, role=user.role),
        user=user_to_info(user),
    )


@router.get('/teachers', response_model=list[TeacherBrief])
async def teachers(db: AsyncSession = Depends(get_db)) -> list[TeacherBrief]:
    rows = await list_teachers(db)
    return [TeacherBrief(id=u.id, username=u.username, display_name=u.display_name) for u in rows]


@router.get('/classes', response_model=list[ClassBrief])
async def classes(db: AsyncSession = Depends(get_db)) -> list[ClassBrief]:
    rows = await list_classes(db)
    return [
        ClassBrief(
            id=cls.id,
            name=cls.name,
            teacher_id=cls.teacher_id,
            teacher_name=teacher.display_name if teacher else "",
            invite_code=cls.invite_code,
        )
        for cls, teacher in rows
    ]


@router.get('/auth/me', response_model=UserInfo)
async def me(current_user=Depends(require_current_user)) -> UserInfo:
    return user_to_info(current_user)


@router.patch('/users/me', response_model=UserInfo)
async def patch_user_me(
    request: UserUpdateRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    try:
        user = await update_user_profile(
            db,
            current_user,
            display_name=request.display_name,
            equipped_title=request.equipped_title,
            study_theme=request.study_theme,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return user_to_info(user)


# ----------------------------- 星系 / 行星 -----------------------------
@router.get('/galaxies', response_model=list[GalaxyOut])
async def galaxies(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[GalaxyOut]:
    return await list_galaxies(db, current_user.id)


@router.get('/galaxies/{slug}', response_model=GalaxyDetailOut)
async def galaxy_detail(slug: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> GalaxyDetailOut:
    detail = await get_galaxy_detail(db, slug, current_user.id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='星系不存在')
    return detail


@router.get('/avatar/state', response_model=AvatarStateOut)
async def avatar_state(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> AvatarStateOut:
    return await get_avatar_state(db, current_user)


@router.get('/avatar/weekly-activity', response_model=WeeklyActivityOut)
async def avatar_weekly_activity(
    current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> WeeklyActivityOut:
    return await get_weekly_activity(db, current_user.id)


@router.get('/planets/{slug}/mastery-trend', response_model=MasteryTrendOut)
async def planet_mastery_trend(
    slug: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> MasteryTrendOut:
    trend = await get_planet_mastery_trend(db, current_user.id, slug)
    if trend is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    return trend


@router.get('/alerts/student', response_model=list[StudentAlertOut])
async def student_alerts(
    current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> list[StudentAlertOut]:
    return await list_student_alerts(db, current_user.id)


@router.get('/orbit/snapshot', response_model=OrbitSnapshotOut)
async def orbit_snapshot(
    current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> OrbitSnapshotOut:
    return await get_orbit_snapshot(db, current_user.id)


@router.post('/avatar/generate', response_model=AvatarGenerateResponse)
async def avatar_generate(
    photo: UploadFile = File(..., description="用户自拍照片"),
    description: str = Form(default="", description="可选自我描述"),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> AvatarGenerateResponse:
    if not photo.content_type or not photo.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传图片文件（jpg/png）")

    image_bytes = await photo.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片内容为空")

    profile_model = await get_latest_profile(db, user_id=current_user.id)
    profile = None
    if profile_model is not None:
        profile = _build_profile_extract(profile_model)

    try:
        result = await generate_avatar(
            image_bytes,
            content_type=photo.content_type or "image/jpeg",
            description=description.strip(),
            profile=profile,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    current_user.avatar_cartoon_url = result["cartoon_url"]
    current_user.avatar_model_url = ""
    db.add(current_user)
    await db.commit()

    return AvatarGenerateResponse(
        status="success",
        cartoon_url=result["cartoon_url"],
        prompt=result["prompt"],
        msg="2D 卡通形象生成完成",
    )


# ----------------------------- 挑战（Teacher / Evaluator） -----------------------------
@router.post('/planets/{slug}/challenge', response_model=ChallengeOut)
async def planet_challenge(
    slug: str,
    review: bool = False,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChallengeOut:
    challenge = await generate_challenge(db, current_user, slug, review=review)
    if challenge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    return challenge


@router.post('/planets/{slug}/lesson-plan', response_model=LessonPlanOut)
async def planet_lesson_plan(
    slug: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> LessonPlanOut:
    from app.services.lesson_plan import generate_lesson_plan

    plan = await generate_lesson_plan(db, slug)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    return plan


@router.post('/challenges/submit', response_model=SubmitChallengeResult)
async def challenge_submit(request: SubmitChallengeRequest, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> SubmitChallengeResult:
    result = await submit_challenge(db, current_user, request)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='题目不存在或无权访问')
    # 学习事件由 challenge.submit_challenge 统一写入，避免与此处双记
    return result


# ----------------------------- AI 领航员（Companion / Tutor） -----------------------------
@router.post('/agents/companion', response_model=CompanionChatResponse)
async def agent_companion(
    request: CompanionChatRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanionChatResponse:
    if request.supervise:
        return await run_companion_supervisor(request, session=db, user=current_user)
    return await companion_chat(request, session=db, user_id=current_user.id)


@router.post('/agents/companion/supervise', response_model=CompanionChatResponse)
async def agent_companion_supervise(
    request: CompanionChatRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> CompanionChatResponse:
    request.supervise = True
    return await run_companion_supervisor(request, session=db, user=current_user)


@router.post('/agents/companion/stream')
async def agent_companion_stream(
    request: CompanionChatRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    _ = current_user

    async def event_stream():
        async for token in companion_chat_stream(
            request, session=db, user_id=str(getattr(current_user, "id", "") or "")
        ):
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.get('/vms/session')
async def vms_session(current_user=Depends(require_current_user)) -> dict:
    """虚拟人交互平台启动参数（按需连接；Secret 仅下发给已登录用户）。"""
    _ = current_user
    settings = get_settings()
    app_id = (settings.xf_vms_app_id or "").strip()
    api_key = (settings.xf_vms_api_key or "").strip()
    api_secret = (settings.xf_vms_api_secret or "").strip()
    scene_id = (settings.xf_vms_scene_id or "").strip()
    if not (app_id and api_key and api_secret and scene_id):
        raise HTTPException(status_code=503, detail='虚拟人交互未配置：请设置 XF_VMS_APP_ID/API_KEY/API_SECRET/SCENE_ID')
    return {
        'appId': app_id,
        'apiKey': api_key,
        'apiSecret': api_secret,
        'sceneId': scene_id,
        'avatarId': (settings.xf_vms_avatar_id or '201293001').strip(),
        'vcn': (settings.xf_vms_vcn or 'x7_langxiao_pro').strip(),
        'serverUrl': (settings.xf_vms_server_url or 'wss://avatar.cn-huadong-1.xf-yun.com/v1/interact').strip(),
        'idleSec': int(settings.xf_vms_idle_sec or 90),
    }


@router.post('/tts')
async def synthesize_tts(
    request: TtsRequest,
    current_user=Depends(require_current_user),
) -> dict:
    """伴学舱口播：讯飞在线 TTS，返回 base64 音频。"""
    _ = current_user
    from app.services.tts_service import synthesize_speech, tts_available

    if not tts_available():
        raise HTTPException(status_code=503, detail='讯飞 TTS 未配置')
    try:
        audio, mime = await synthesize_speech(request.text, request.vcn or None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc) or 'TTS 合成失败') from exc
    import base64

    return {
        'mime': mime,
        'audio_base64': base64.b64encode(audio).decode('ascii'),
        'chars': len(request.text),
    }


@router.post('/archive/polish')
async def archive_polish(
    request: Request,
    current_user=Depends(require_current_user),
) -> dict:
    from app.services.archive_service import extract_document_text, polish_archive_text

    content_type = request.headers.get("content-type", "")
    text = ""
    if "multipart/form-data" in content_type:
        form = await request.form()
        text = str(form.get("text") or "")
        upload = form.get("file")
        if upload and hasattr(upload, "read"):
            data = await upload.read()
            if len(data) > 15 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="文件不能超过 15 MB")
            try:
                text = extract_document_text(str(getattr(upload, "filename", "")), data)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        try:
            payload = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="请求内容不是有效 JSON") from exc
        text = str(payload.get("text") or "") if isinstance(payload, dict) else ""

    try:
        return await polish_archive_text(text)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('/agents/oral', response_model=OralPracticeOut)
async def agent_oral(
    request: OralPracticeIn,
    current_user=Depends(require_current_user),
) -> OralPracticeOut:
    from app.services.oral_practice import oral_practice

    return await oral_practice(request)


@router.post('/agents/oral-audio', response_model=OralPracticeOut)
async def agent_oral_audio(
    cabin: str = Form(...),
    mode: str = Form('speaking'),
    duration_sec: int = Form(0),
    transcript: str = Form(''),
    ref_text: str = Form(''),
    file: UploadFile = File(...),
    current_user=Depends(require_current_user),
) -> OralPracticeOut:
    from app.core.paths import ORAL_DIR
    from app.services.oral_practice import oral_practice_with_audio
    from app.services.upload_service import save_upload_bytes

    if not cabin.strip():
        raise HTTPException(status_code=400, detail='舱位不能为空')
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail='文件为空')
    try:
        audio_url = save_upload_bytes(
            raw_bytes,
            ORAL_DIR,
            'oral',
            file.filename or 'oral.webm',
            file.content_type or '',
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await oral_practice_with_audio(
        cabin.strip(),
        mode or 'speaking',
        int(duration_sec or 0),
        audio_url,
        audio_bytes=raw_bytes,
        audio_filename=file.filename or 'oral.webm',
        audio_content_type=file.content_type or '',
        transcript=transcript or '',
        ref_text=ref_text or '',
    )


@router.get('/planets/{slug}/fragments', response_model=FragmentProgress)
async def planet_fragments(
    slug: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> FragmentProgress:
    from sqlalchemy import select
    from app.models.galaxy import Planet
    from app.models.mastery import PlanetMastery

    planet = (await db.execute(select(Planet).where(Planet.slug == slug))).scalar_one_or_none()
    if planet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    mastery = (
        await db.execute(
            select(PlanetMastery).where(
                PlanetMastery.user_id == current_user.id, PlanetMastery.planet_id == planet.id
            )
        )
    ).scalar_one_or_none()
    progress = get_fragment_progress(mastery)
    return FragmentProgress(**progress)


@router.post('/planets/{slug}/review', response_model=ReviewPlanetResult)
async def planet_review(
    slug: str,
    request: ReviewPlanetRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReviewPlanetResult:
    from sqlalchemy import select
    from app.models.galaxy import Planet

    planet = (await db.execute(select(Planet).where(Planet.slug == slug))).scalar_one_or_none()
    if planet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    result = await review_planet(db, current_user, planet.id, request.correct)
    if result is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='该行星暂不可复习')
    return ReviewPlanetResult(**result)


# ----------------------------- 引力黑洞初测 -----------------------------
@router.post('/galaxies/{slug}/assessment/start', response_model=AssessmentStartOut)
async def galaxy_assessment_start(
    slug: str, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> AssessmentStartOut:
    result = await start_assessment(db, current_user, slug)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='星系不存在')
    return AssessmentStartOut(**result)


@router.post('/galaxies/{slug}/assessment/submit', response_model=AssessmentSubmitOut)
async def galaxy_assessment_submit(
    slug: str,
    request: AssessmentSubmitRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssessmentSubmitOut:
    result = await submit_assessment_answer(db, current_user, request.assessment_id, request.selected_key)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='测评会话不存在')
    return AssessmentSubmitOut(**result)


# ----------------------------- 星座成就 -----------------------------
@router.get('/constellations', response_model=list[ConstellationOut])
async def constellations(
    current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> list[ConstellationOut]:
    items = await list_constellations(db, current_user.id)
    return [ConstellationOut(**c) for c in items]


# ----------------------------- 社交：排行榜 / 好友 / 虫洞 -----------------------------
@router.get('/social/leaderboard', response_model=list[LeaderboardItem])
async def leaderboard(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[LeaderboardItem]:
    return await social_service.leaderboard(db, current_user.id)


@router.get('/social/friends', response_model=list[FriendItem])
async def friends(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[FriendItem]:
    return await social_service.list_friends(db, current_user.id)


@router.post('/social/friends', response_model=FriendItem)
async def add_friend(request: AddFriendRequest, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> FriendItem:
    friend = await social_service.add_friend(db, current_user.id, request.username)
    if friend is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='用户不存在或不能添加自己')
    return friend


@router.get('/social/wormhole', response_model=list[WormholeMessageOut])
async def wormhole_inbox(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[WormholeMessageOut]:
    return await social_service.list_wormhole(db, current_user.id)


@router.post('/social/wormhole')
async def wormhole_send(request: WormholeSendRequest, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    msg = await social_service.send_wormhole(db, current_user.id, request.receiver_id, request.content)
    return {'ok': True, 'id': msg.id}


@router.post('/social/sos')
async def sos_emit(
    request: SosEmitRequest, current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    result = await emit_sos(db, current_user, request.planet_slug)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    return result


@router.get('/social/sos')
async def sos_list(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await list_sos(db, current_user.id)


@router.post('/social/sos/{beacon_id}/respond')
async def sos_respond(
    beacon_id: str,
    request: SosRespondRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await respond_sos(db, current_user, beacon_id, request.content)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='求救信号不存在')
    return result


@router.get('/alerts/rescue')
async def rescue_alerts(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[dict]:
    """学生端获取教师投放的救援 AI 助手上下文。"""
    from sqlalchemy import select
    from app.models.alert import Alert

    rows = (
        await db.execute(
            select(Alert)
            .where(Alert.student_id == current_user.id, Alert.alert_type == "rescue_assistant", Alert.resolved.is_(False))
            .order_by(Alert.created_at.desc())
            .limit(10)
        )
    ).scalars().all()
    return [{"id": a.id, "message": a.message, "created_at": a.created_at.isoformat() if a.created_at else None} for a in rows]


# ----------------------------- 教师端 -----------------------------
@router.get('/teacher/classes', response_model=list[ClassBriefOut])
async def teacher_classes(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[ClassBriefOut]:
    return await teacher_service.list_teacher_classes(db, current_user)


@router.get('/teacher/gate-policy', response_model=GatePolicyOut)
async def teacher_get_gate_policy(
    class_id: str = '',
    galaxy_slug: str = '',
    current_user=Depends(require_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
) -> GatePolicyOut:
    from app.services.gate_policy import default_thresholds, get_policy, policy_to_dict

    cid = (class_id or '').strip()
    if not cid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='缺少 class_id')
    allowed = await teacher_service._class_ids_for_teacher(db, current_user, cid)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权访问该班级')
    row = await get_policy(db, cid, galaxy_slug, create_if_missing=True)
    if row is None:
        thr = default_thresholds()
        return GatePolicyOut(class_id=cid, galaxy_slug=galaxy_slug or '', **thr)
    return GatePolicyOut(**policy_to_dict(row))


@router.put('/teacher/gate-policy', response_model=GatePolicyOut)
async def teacher_put_gate_policy(
    body: GatePolicyUpdate,
    current_user=Depends(require_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
) -> GatePolicyOut:
    from app.services.gate_policy import policy_to_dict, upsert_policy

    cid = (body.class_id or '').strip()
    if not cid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='缺少 class_id')
    allowed = await teacher_service._class_ids_for_teacher(db, current_user, cid)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权修改该班级')
    try:
        row = await upsert_policy(
            db,
            class_id=cid,
            galaxy_slug=body.galaxy_slug or '',
            practice_questions=body.practice_questions,
            practice_min_correct=body.practice_min_correct,
            explain_pass_threshold=body.explain_pass_threshold,
            apply_required_default=body.apply_required_default,
            learn_evidence_min=body.learn_evidence_min,
            decay_days=body.decay_days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GatePolicyOut(**policy_to_dict(row))


@router.get('/teacher/overview', response_model=ClassOverviewOut)
async def teacher_overview(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ClassOverviewOut:
    return await teacher_service.class_overview(db, current_user, class_id)


@router.get('/teacher/risks', response_model=list[StudentRiskItem])
async def teacher_risks(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[StudentRiskItem]:
    return await teacher_service.student_risks(db, current_user, class_id)


@router.get('/teacher/review-tickets')
async def teacher_review_tickets(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.hallucination_tickets import list_pending_tickets

    return await list_pending_tickets(db, current_user, class_id=class_id)


@router.post('/teacher/review-tickets/{ticket_id}/resolve')
async def teacher_resolve_review_ticket(
    ticket_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.hallucination_tickets import resolve_ticket

    result = await resolve_ticket(db, current_user, ticket_id)
    if result is None:
        raise HTTPException(status_code=404, detail='工单不存在')
    return result


@router.post('/teacher/dispatch', response_model=DispatchTaskResponse)
async def teacher_dispatch(
    request: DispatchTaskRequest,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> DispatchTaskResponse:
    return await teacher_service.dispatch_task(db, current_user, request)


@router.post('/teacher/review-scan', response_model=ReviewScanOut)
async def teacher_review_scan(
    request: ReviewScanRequest,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ReviewScanOut:
    """按班级 GatePolicy 衰减天数扫描并派发复习 DailyTask。"""
    from app.services.memory_decay import scan_and_dispatch_reviews

    cid = (request.class_id or '').strip()
    if not cid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='缺少 class_id')
    allowed = await teacher_service._class_ids_for_teacher(db, current_user, cid)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权扫描该班级')
    try:
        result = await scan_and_dispatch_reviews(db, current_user, cid)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ReviewScanOut(**result)


@router.get('/teacher/students/{student_id}/learning-story')
async def teacher_student_learning_story(
    student_id: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await teacher_extras_service.learning_story(db, current_user, student_id, class_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在或无权查看')
    return data


@router.get('/teacher/grades/export')
async def teacher_grades_export(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """服务端导出成绩册 CSV（带 BOM，Excel 可直接打开）。"""
    from datetime import datetime, timezone

    from fastapi.responses import Response

    cid = (class_id or '').strip()
    if not cid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='缺少 class_id')
    allowed = await teacher_service._class_ids_for_teacher(db, current_user, cid)
    if not allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权导出该班级')
    rows = await teacher_extras_service.gradebook(db, current_user, cid)
    csv_text = teacher_extras_service.gradebook_to_csv(rows)
    filename = f"grades_{cid[:8]}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(
        content=csv_text.encode('utf-8'),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@router.post('/teacher/roster/import')
async def teacher_roster_import_csv(
    class_id: str = Form(...),
    file: UploadFile = File(...),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """CSV 花名册导入：username,display_name[,password]。"""
    from sqlalchemy import select

    from app.models.school_class import SchoolClass
    from app.schemas.admin import ImportStudentsRequest, ImportStudentItem

    cid = (class_id or '').strip()
    if not cid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='请指定班级')
    cls = (
        await db.execute(
            select(SchoolClass).where(SchoolClass.id == cid, SchoolClass.teacher_id == current_user.id)
        )
    ).scalar_one_or_none()
    if cls is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权向该班级导入学生')

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='文件为空')
    parsed = teacher_extras_service.parse_roster_csv(raw)
    if not parsed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='CSV 无有效行，请使用 用户名,姓名')

    payload = ImportStudentsRequest(
        students=[ImportStudentItem(**s) for s in parsed],
        class_id=cid,
        teacher_id=current_user.id,
    )
    result = await admin_service.import_students(db, payload)
    return {
        'ok': True,
        'created': result.created,
        'skipped': result.skipped,
        'parsed': len(parsed),
        'filename': file.filename or '',
    }


@router.get('/teacher/profile-matrix', response_model=ProfileMatrixOut)
async def teacher_profile_matrix(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ProfileMatrixOut:
    return await teacher_service.class_profile_matrix(db, current_user, class_id)


@router.get('/teacher/gravity-wells', response_model=list[GravityWellItem])
async def teacher_gravity_wells(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[GravityWellItem]:
    return await teacher_service.gravity_wells(db, current_user, class_id)


@router.post('/teacher/intervene', response_model=InterventionResponse)
async def teacher_intervene(
    request: InterventionRequest,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> InterventionResponse:
    return await teacher_service.intervene(db, current_user, request)


@router.get('/teacher/students/{student_id}/detail')
async def teacher_student_detail(
    student_id: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    data = await teacher_extras_service.student_detail(db, current_user, student_id, class_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在或无权查看')
    return data


async def _teacher_assert_student(db: AsyncSession, teacher, student_id: str, class_id: str = '') -> None:
    ok = await teacher_extras_service.student_accessible(db, teacher, student_id, class_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在或无权查看')


@router.get('/teacher/students/{student_id}/focus/summary', response_model=FocusSummaryOut)
async def teacher_student_focus_summary(
    student_id: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> FocusSummaryOut:
    await _teacher_assert_student(db, current_user, student_id, class_id)
    return FocusSummaryOut(**(await focus_summary(db, student_id)))


@router.get('/teacher/students/{student_id}/focus/heatmap', response_model=FocusHeatmapOut)
async def teacher_student_focus_heatmap(
    student_id: str,
    class_id: str = '',
    week_offset: int = 0,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> FocusHeatmapOut:
    await _teacher_assert_student(db, current_user, student_id, class_id)
    return FocusHeatmapOut(**(await focus_heatmap(db, student_id, week_offset)))


@router.get('/teacher/students/{student_id}/focus/yearly')
async def teacher_student_focus_yearly(
    student_id: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _teacher_assert_student(db, current_user, student_id, class_id)
    return await focus_yearly_calendar(db, student_id)


@router.get('/teacher/students/{student_id}/learn-heatmap')
async def teacher_student_learn_heatmap(
    student_id: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """学闸证据热力（划词提问次数 + 按日/按 kind 摘要），与学生成长报告同口径。"""
    from sqlalchemy import select

    from app.models.mastery import PlanetMastery
    from app.models.user import User
    from app.services.evaluation import _aggregate_learn_evidence

    await _teacher_assert_student(db, current_user, student_id, class_id)
    student = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在')
    mastery_rows = (
        await db.execute(select(PlanetMastery).where(PlanetMastery.user_id == student_id))
    ).scalars().all()
    selection_ask_count, learn_heatmap_summary = _aggregate_learn_evidence(list(mastery_rows))
    return {
        'student_id': student_id,
        'display_name': student.display_name or student.username,
        'selection_ask_count': selection_ask_count,
        'learn_heatmap_summary': learn_heatmap_summary,
    }


@router.get('/teacher/students/{student_id}/evaluation-report', response_model=EvaluationReportOut)
async def teacher_student_evaluation_report(
    student_id: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> EvaluationReportOut:
    from sqlalchemy import select

    from app.models.user import User

    await _teacher_assert_student(db, current_user, student_id, class_id)
    student = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在')
    return await build_evaluation_report(db, student)


@router.get('/teacher/students/{student_id}/vault/tree')
async def teacher_student_vault_tree(
    student_id: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import select

    from app.models.user import User
    from app.services import vault_service as vault

    await _teacher_assert_student(db, current_user, student_id, class_id)
    student = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在')
    await vault.ensure_vault(db, student)
    return {'tree': vault.build_tree(student.id), 'student_id': student_id}


@router.get('/teacher/students/{student_id}/vault/file')
async def teacher_student_vault_file(
    student_id: str,
    path: str,
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import select

    from app.models.user import User
    from app.services import vault_service as vault

    await _teacher_assert_student(db, current_user, student_id, class_id)
    student = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在')
    try:
        return await vault.read_file(db, student, path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/teacher/students/{student_id}/vault/search')
async def teacher_student_vault_search(
    student_id: str,
    q: str = '',
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from sqlalchemy import select

    from app.models.user import User
    from app.services import vault_service as vault

    await _teacher_assert_student(db, current_user, student_id, class_id)
    student = (await db.execute(select(User).where(User.id == student_id))).scalar_one_or_none()
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='学生不存在')
    hits = await vault.search_files(db, student, q)
    return {'results': hits, 'student_id': student_id}


@router.get('/teacher/insight/overview')
async def teacher_insight_overview(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_extras_service.insight_overview(db, current_user, class_id)


@router.get('/teacher/gradebook', response_model=list[GradebookRow])
async def teacher_gradebook(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[GradebookRow]:
    rows = await teacher_extras_service.gradebook(db, current_user, class_id)
    return [GradebookRow(**r) for r in rows]


@router.post('/teacher/broadcast', response_model=BroadcastOut)
async def teacher_broadcast(
    request: BroadcastIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> BroadcastOut:
    try:
        data = await teacher_extras_service.broadcast_to_class(
            db, current_user, request.class_id, request.title, request.body
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BroadcastOut(
        id=data['id'],
        class_id=request.class_id,
        title=request.title,
        body=request.body,
        recipient_count=data['recipient_count'],
        created_at=data['created_at'],
    )


@router.get('/teacher/broadcasts', response_model=list[BroadcastOut])
async def teacher_broadcasts(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[BroadcastOut]:
    rows = await teacher_extras_service.list_broadcasts(db, current_user, class_id)
    return [BroadcastOut(**r) for r in rows]


@router.get('/teacher/attendance', response_model=list[AttendanceRow])
async def teacher_attendance_list(
    class_id: str,
    record_date: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[AttendanceRow]:
    from datetime import date

    day = record_date or date.today().isoformat()
    rows = await teacher_extras_service.list_attendance(db, current_user, class_id, day)
    return [AttendanceRow(**r) for r in rows]


@router.post('/teacher/attendance/checkin')
async def teacher_attendance_checkin(
    request: AttendanceSetIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import date

    day = request.record_date or date.today().isoformat()
    return await teacher_extras_service.set_attendance(
        db, current_user, request.class_id, request.student_id, request.status, day
    )


@router.post('/teacher/assignments', response_model=AssignmentOut)
async def teacher_create_assignment(
    request: AssignmentCreateIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentOut:
    due_at = None
    if request.due_at:
        from datetime import datetime

        try:
            due_at = datetime.fromisoformat(request.due_at.replace('Z', '+00:00'))
        except ValueError:
            pass
    row = await teacher_extras_service.create_assignment(
        db,
        current_user,
        class_id=request.class_id,
        title=request.title,
        description=request.description,
        galaxy_slug=request.galaxy_slug,
        due_at=due_at,
        questions=request.questions,
        source_resource_id=request.source_resource_id,
    )
    return AssignmentOut(**row)


@router.post('/teacher/assignments/extract-questions', response_model=AssignmentExtractOut)
async def teacher_extract_assignment_questions(
    file: UploadFile = File(...),
    hint_title: str = Form(''),
    current_user=Depends(require_teacher),
) -> AssignmentExtractOut:
    from app.services.assignment_extract import extract_questions_from_upload

    _ = current_user
    data = await file.read()
    result = await extract_questions_from_upload(
        filename=file.filename or 'upload.bin',
        data=data,
        content_type=file.content_type or '',
        hint_title=hint_title,
    )
    return AssignmentExtractOut(**result)


@router.post('/teacher/assignments/extract-from-resource', response_model=AssignmentExtractOut)
async def teacher_extract_from_resource(
    resource_id: str = Form(...),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssignmentExtractOut:
    from sqlalchemy import select

    from app.models.note import LessonResource
    from app.services.assignment_extract import extract_questions_from_resource_file

    row = (
        await db.execute(
            select(LessonResource).where(
                LessonResource.id == resource_id,
                LessonResource.teacher_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='知识库资料不存在')
    result = await extract_questions_from_resource_file(row.file_url, hint_title=row.title)
    return AssignmentExtractOut(**result)


@router.get('/teacher/assignments', response_model=list[AssignmentOut])
async def teacher_list_assignments(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentOut]:
    rows = await teacher_extras_service.list_teacher_assignments(db, current_user, class_id)
    return [AssignmentOut(**r) for r in rows]


@router.get('/teacher/assignments/{assignment_id}/submissions', response_model=list[SubmissionOut])
async def teacher_assignment_submissions(
    assignment_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[SubmissionOut]:
    rows = await teacher_extras_service.list_submissions(db, current_user, assignment_id)
    return [SubmissionOut(**r) for r in rows]


@router.post('/teacher/assignments/{assignment_id}/submissions/{submission_id}/grade')
async def teacher_grade_submission(
    assignment_id: str,
    submission_id: str,
    request: GradeSubmissionIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_extras_service.grade_submission(
            db, current_user, assignment_id, submission_id, request.score, request.feedback
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/assignments', response_model=list[AssignmentOut])
async def student_assignments(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AssignmentOut]:
    rows = await teacher_extras_service.list_student_assignments(db, current_user)
    return [AssignmentOut(**r) for r in rows]


@router.post('/assignments/{assignment_id}/submit')
async def student_submit_assignment(
    assignment_id: str,
    request: AssignmentSubmitIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_extras_service.submit_assignment(
            db, current_user, assignment_id, request.content, request.attachment_url
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/teacher/students/import', response_model=ImportStudentsResponse)
async def teacher_import_students(
    request: ImportStudentsRequest,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ImportStudentsResponse:
    """教师批量导入学生到自己的班级。"""
    from sqlalchemy import select

    from app.models.school_class import SchoolClass

    class_id = (request.class_id or '').strip()
    if not class_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='请指定班级')
    cls = (
        await db.execute(
            select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.teacher_id == current_user.id)
        )
    ).scalar_one_or_none()
    if cls is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权向该班级导入学生')
    payload = ImportStudentsRequest(
        students=request.students,
        class_id=class_id,
        teacher_id=current_user.id,
    )
    return await admin_service.import_students(db, payload)


@router.post('/teacher/galaxies/forge')
async def teacher_forge_galaxy(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """教师从 PDF 锻造知识星系。"""
    _ = current_user
    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='文件为空')
    result = await forge_galaxy_from_pdf(db, data, title_hint=title or file.filename or "")
    return {"ok": True, **result}


@router.delete('/teacher/planets/{slug}')
async def teacher_delete_planet(slug: str, current_user=Depends(require_teacher), db: AsyncSession = Depends(get_db)) -> dict:
    _ = current_user
    ok = await admin_service.delete_planet(db, slug)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    return {'ok': True, 'slug': slug}


# ----------------------------- 管理员端 -----------------------------
@router.post('/admin/students/import', response_model=ImportStudentsResponse)
async def admin_import_students(request: ImportStudentsRequest, http_request: Request, admin_user=Depends(require_admin), db: AsyncSession = Depends(get_db)) -> ImportStudentsResponse:
    from app.services.audit import record_audit

    result = await admin_service.import_students(db, request)
    await record_audit(
        db,
        user=admin_user,
        action='import_students',
        target_type='user',
        detail={'created': result.created, 'skipped': result.skipped, 'class_id': request.class_id},
        request=http_request,
    )
    return result


@router.post('/admin/galaxies')
async def admin_upsert_galaxy(request: GalaxyUpsertRequest, http_request: Request, admin_user=Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.audit import record_audit

    galaxy = await admin_service.upsert_galaxy(db, request)
    await record_audit(
        db, user=admin_user, action='upsert_galaxy', target_type='galaxy', target_id=galaxy.slug, request=http_request
    )
    return {'ok': True, 'id': galaxy.id, 'slug': galaxy.slug}


@router.post('/admin/planets')
async def admin_upsert_planet(request: PlanetUpsertRequest, http_request: Request, admin_user=Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.audit import record_audit

    planet = await admin_service.upsert_planet(db, request)
    if planet is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='所属星系不存在')
    await record_audit(
        db, user=admin_user, action='upsert_planet', target_type='planet', target_id=planet.slug, request=http_request
    )
    return {'ok': True, 'id': planet.id, 'slug': planet.slug}


@router.delete('/admin/planets/{slug}')
async def admin_delete_planet(slug: str, http_request: Request, admin_user=Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.audit import record_audit

    ok = await admin_service.delete_planet(db, slug)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='行星不存在')
    await record_audit(
        db, user=admin_user, action='delete_planet', target_type='planet', target_id=slug, request=http_request
    )
    return {'ok': True, 'slug': slug}


@router.get('/admin/galaxies', response_model=list[GalaxyBrief])
async def admin_list_galaxies(_: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[GalaxyBrief]:
    return await admin_service.list_galaxies(db)


@router.get('/admin/planets', response_model=list[PlanetBrief])
async def admin_list_planets(galaxy_slug: str = '', _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[PlanetBrief]:
    return await admin_service.list_planets(db, galaxy_slug=galaxy_slug)


@router.get('/admin/overview', response_model=SystemOverviewOut)
async def admin_overview(_: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> SystemOverviewOut:
    return await admin_service.system_overview(db)


@router.get('/admin/users', response_model=list[UserAdminItem])
async def admin_list_users(role: str = '', _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[UserAdminItem]:
    return await admin_service.list_users(db, role=role)


@router.patch('/admin/users/{user_id}', response_model=UserAdminItem)
async def admin_update_user(user_id: str, request: UserAdminUpdateRequest, http_request: Request, admin_user=Depends(require_admin), db: AsyncSession = Depends(get_db)) -> UserAdminItem:
    from app.services.audit import record_audit

    if request.role is not None and request.role not in {'student', 'teacher', 'admin'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='非法角色')
    user = await admin_service.update_user(db, user_id, request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在')
    await record_audit(
        db,
        user=admin_user,
        action='update_user',
        target_type='user',
        target_id=user.username,
        detail=request.model_dump(exclude_none=True),
        request=http_request,
    )
    return user


@router.get('/admin/usage', response_model=list[ApiUsageSummary])
async def admin_usage(days: int = 7, _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[ApiUsageSummary]:
    return await admin_service.list_usage_summary(db, days=days)


@router.get('/admin/errors', response_model=list[ApiErrorItem])
async def admin_errors(limit: int = 50, _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[ApiErrorItem]:
    return await admin_service.list_api_errors(db, limit=limit)


@router.get('/admin/maintenance', response_model=MaintenanceOut)
async def admin_get_maintenance(_: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> MaintenanceOut:
    return await admin_service.get_maintenance(db)


@router.patch('/admin/maintenance', response_model=MaintenanceOut)
async def admin_update_maintenance(request: MaintenanceUpdateRequest, http_request: Request, admin_user=Depends(require_admin), db: AsyncSession = Depends(get_db)) -> MaintenanceOut:
    from app.services.audit import record_audit

    result = await admin_service.update_maintenance(db, request)
    await record_audit(
        db,
        user=admin_user,
        action='update_maintenance',
        target_type='system',
        detail={'enabled': request.enabled},
        request=http_request,
    )
    return result


@router.get('/system/status', response_model=MaintenanceOut)
async def system_status(db: AsyncSession = Depends(get_db)) -> MaintenanceOut:
    from app.services import runtime_config

    result = await admin_service.get_maintenance(db)
    result.features = runtime_config.feature_flags()
    return result


@router.get('/admin/quota', response_model=ApiQuotaOut)
async def admin_quota(_: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> ApiQuotaOut:
    return await admin_service.api_quota(db)


@router.get('/admin/agent-runs', response_model=list[AgentRunOut])
async def admin_agent_runs(
    limit: int = 50,
    scene: str = '',
    mode: str = '',
    status_filter: str = '',
    user_id: str = '',
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AgentRunOut]:
    from app.services import agent_trace

    rows = await agent_trace.list_agent_runs(
        db,
        limit=limit,
        scene=scene,
        mode=mode,
        status=status_filter,
        user_id=user_id,
    )
    return [
        AgentRunOut(
            id=r.id,
            user_id=r.user_id,
            user_name=r.user_name,
            scene=r.scene,
            mode=r.mode,
            status=r.status,
            topic=r.topic,
            graph_plan=r.graph_plan or {},
            current_step=r.current_step,
            current_agent=r.current_agent,
            error_message=r.error_message,
            created_at=r.created_at.isoformat() if r.created_at else '',
            finished_at=r.finished_at.isoformat() if r.finished_at else '',
            steps=[],
        )
        for r in rows
    ]


@router.post('/admin/agent-runs/seed-modes')
async def admin_agent_runs_seed_modes(
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """注入四模式演示 run（不调用 LLM），供观测页对比。

    注意：必须声明在 `/admin/agent-runs/{run_id}` 之前，否则 seed-modes 会被当成 run_id，
    POST 命中仅允许 GET 的详情路由 → 405 Method Not Allowed。
    """
    from app.services import agent_trace

    created = await agent_trace.seed_demo_mode_runs(db)
    return {"ok": True, "created": created, "count": len(created)}


@router.get('/admin/agent-runs/{run_id}', response_model=AgentRunOut)
async def admin_agent_run_detail(
    run_id: str,
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AgentRunOut:
    from app.services import agent_trace

    detail = await agent_trace.get_agent_run_detail(db, run_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Agent run 不存在')
    return AgentRunOut(**detail)


@router.get('/admin/demo-health')
async def admin_demo_health(
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """路演上场预检：LLM / RAG / DB。"""
    from app.services.demo_health import build_demo_health

    return await build_demo_health(db)


@router.get('/admin/harness')
async def admin_harness_report(_: object = Depends(require_admin)) -> dict:
    """只读返回 Better Harness 产物元信息（不在服务端重跑）。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[3] / 'docs' / 'evidence' / 'better-harness'
    files = {}
    for name in ('report.html', 'report.md', 'findings.json', 'README.md'):
        p = root / name
        files[name] = {
            'exists': p.is_file(),
            'size': p.stat().st_size if p.is_file() else 0,
            'path': f'docs/evidence/better-harness/{name}',
        }
    return {
        'root': 'docs/evidence/better-harness',
        'files': files,
        'note': '开发侧用 Better Harness CLI 生成报告后放入该目录；本接口仅只读展示元数据。',
        'reproduce': '见 docs/evidence/better-harness/README.md',
    }


@router.get('/admin/harness/findings')
async def admin_harness_findings(_: object = Depends(require_admin)) -> dict:
    """只读返回 findings.json（供管理端原生渲染五维与发现卡片）。"""
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[3] / 'docs' / 'evidence' / 'better-harness' / 'findings.json'
    if not p.is_file():
        return {
            'status': 'missing',
            'project': 'SparkOrbit',
            'note': 'findings.json 不存在；缺证据显式标注',
            'dimensions': [],
            'findings': [],
        }
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {'status': 'invalid', 'dimensions': [], 'findings': [], 'note': 'findings.json 格式无效'}
        return _normalize_harness_findings(data)
    except Exception as exc:  # noqa: BLE001
        return {
            'status': 'error',
            'dimensions': [],
            'findings': [],
            'note': f'读取 findings 失败：{exc}',
        }


def _normalize_harness_findings(data: dict) -> dict:
    """将官方 CLI / 本地扫描器产物规范为 AdminHarness 字段。"""
    out = dict(data)
    if not out.get('status'):
        out['status'] = 'ok'
    if not out.get('project'):
        out['project'] = 'SparkOrbit'
    raw = out.get('findings') or []
    if not isinstance(raw, list):
        raw = []
    normalized = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        cause = str(item.get('cause') or item.get('summary') or item.get('description') or '')
        expected = str(item.get('expected') or item.get('expectation') or item.get('should') or '')
        repair = str(item.get('repair') or item.get('fix') or item.get('action') or '')
        normalized.append(
            {
                **item,
                'id': str(item.get('id') or f'finding-{i + 1}'),
                'priority': str(item.get('priority') or 'medium'),
                'dimension': str(item.get('dimension') or item.get('dim') or item.get('category') or 'evidence'),
                'title': str(item.get('title') or item.get('name') or f'发现 {i + 1}'),
                'cause': cause,
                'expected': expected or '见仓库约定 / AGENTS.md',
                'repair': repair or '按 Cause 补齐后重跑 Harness',
                'summary': str(item.get('summary') or cause),
            }
        )
    out['findings'] = normalized
    dims = out.get('dimensions') or []
    if isinstance(dims, list):
        out['dimensions'] = dims
    else:
        out['dimensions'] = []
    return out


@router.get('/admin/harness/report.html')
async def admin_harness_report_html(_: object = Depends(require_admin)):
    from pathlib import Path

    from fastapi.responses import FileResponse, HTMLResponse

    p = Path(__file__).resolve().parents[3] / 'docs' / 'evidence' / 'better-harness' / 'report.html'
    if not p.is_file():
        return HTMLResponse(
            '<!doctype html><meta charset="utf-8"><title>Harness</title>'
            '<body style="font-family:sans-serif;padding:2rem;background:#0b1220;color:#e2e8f0">'
            '<h1>尚未生成 Better Harness 报告</h1>'
            '<p>请按 <code>docs/evidence/better-harness/README.md</code> 复现命令生成后刷新本页。</p>'
            '</body>',
            status_code=200,
        )
    return FileResponse(p, media_type='text/html; charset=utf-8')


@router.post('/admin/galaxies/forge')
async def admin_forge_galaxy(
    http_request: Request,
    file: UploadFile = File(...),
    title: str = Form(default=""),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import record_audit

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='文件为空')
    result = await forge_galaxy_from_pdf(db, data, title_hint=title or file.filename or "")
    await record_audit(
        db,
        user=admin_user,
        action='forge_galaxy',
        target_type='galaxy',
        target_id=str(result.get('galaxy_slug', ''))[:100],
        detail={'filename': file.filename or '', 'title': title},
        request=http_request,
    )
    return {"ok": True, **result}


# ----------------------------- 管理员端：安全运营（审计 / 告警 / 日报 / 分析 / 配置 / 工单） -----------------------------
@router.get('/admin/audit-logs')
async def admin_audit_logs(
    action: str = '',
    username: str = '',
    days: int = 7,
    limit: int = 100,
    offset: int = 0,
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import list_audit_logs

    return await list_audit_logs(db, action=action, username=username, days=days, limit=limit, offset=offset)


@router.get('/admin/login-logs')
async def admin_login_logs(
    username: str = '',
    success: str = '',
    days: int = 7,
    limit: int = 100,
    offset: int = 0,
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import list_login_logs

    return await list_login_logs(db, username=username, success=success, days=days, limit=limit, offset=offset)


@router.get('/admin/alerts')
async def admin_alerts(
    status_filter: str = '',
    level: str = '',
    limit: int = 100,
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.system_alerts import list_alerts

    return await list_alerts(db, status=status_filter, level=level, limit=limit)


@router.post('/admin/alerts/scan')
async def admin_alerts_scan(_: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.system_alerts import scan_alerts

    created = await scan_alerts(db)
    return {'ok': True, 'created': created, 'count': len(created)}


@router.patch('/admin/alerts/{alert_id}')
async def admin_update_alert(
    alert_id: str,
    http_request: Request,
    new_status: str = Body(..., embed=True, alias='status'),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import record_audit
    from app.services.system_alerts import update_alert

    result = await update_alert(db, alert_id, new_status)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='告警不存在或状态非法')
    await record_audit(
        db,
        user=admin_user,
        action='update_alert',
        target_type='alert',
        target_id=alert_id,
        detail={'status': new_status},
        request=http_request,
    )
    return result


@router.post('/admin/alerts/{alert_id}/triage')
async def admin_triage_alert(
    alert_id: str,
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.system_alerts import triage_alert

    result = await triage_alert(db, alert_id, user_id=admin_user.id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='告警不存在')
    return result


@router.get('/admin/reports')
async def admin_security_reports(
    limit: int = 30, _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    from app.services.security_report import list_reports

    return await list_reports(db, limit=limit)


@router.post('/admin/reports/generate')
async def admin_generate_report(
    report_date: str = Body(default='', embed=True),
    force: bool = Body(default=False, embed=True),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from datetime import date as _date, datetime as _dt, timezone as _tz

    from app.services.security_report import generate_report

    target = (report_date or '').strip() or _dt.now(_tz.utc).date().isoformat()
    try:
        _date.fromisoformat(target)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='日期格式应为 YYYY-MM-DD')
    return await generate_report(db, target, force=force, user_id=admin_user.id)


@router.get('/admin/reports/{report_date}')
async def admin_security_report_detail(
    report_date: str, _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict:
    from app.services.security_report import get_report

    result = await get_report(db, report_date)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='该日期尚无日报')
    return result


@router.get('/admin/analytics')
async def admin_analytics(_: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> dict:
    from app.services.analytics import build_analytics

    return await build_analytics(db)


@router.get('/admin/settings')
async def admin_list_settings(_: object = Depends(require_admin), db: AsyncSession = Depends(get_db)) -> list[dict]:
    from app.services import runtime_config

    return await runtime_config.list_settings(db)


@router.patch('/admin/settings')
async def admin_update_settings(
    http_request: Request,
    values: dict = Body(...),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services import runtime_config
    from app.services.audit import record_audit

    result = await runtime_config.update_settings(db, {k: str(v) for k, v in values.items()})
    await record_audit(
        db,
        user=admin_user,
        action='update_settings',
        target_type='system',
        detail={'keys': sorted(values.keys())},
        request=http_request,
    )
    return result


@router.get('/admin/jobs')
async def admin_jobs(_: object = Depends(require_admin)) -> list[dict]:
    from app.services.ops_jobs import job_status

    return await job_status()


@router.get('/admin/providers')
async def admin_list_providers(
    _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    """API 平台列表：配置状态、掩码 Key（永不返回明文）、模型、余额快照。"""
    from app.services.provider_status import list_providers

    return await list_providers(db)


@router.patch('/admin/providers/{provider}')
async def admin_update_provider(
    provider: str,
    http_request: Request,
    api_key: str = Body(default='', embed=True),
    model: str = Body(default='', embed=True),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """在线更换 API Key / 模型：写 override:* 覆盖层，客户端自动重建。"""
    from app.services.audit import record_audit
    from app.services.provider_status import mask_key, update_provider

    result = await update_provider(db, provider, api_key=api_key, model=model)
    if not result.get('ok'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get('error', '更新失败'))
    await record_audit(
        db,
        user=admin_user,
        action='update_provider_key',
        target_type='provider',
        target_id=provider,
        detail={
            'key_changed': bool(api_key.strip()),
            'key_masked': mask_key(api_key) if api_key.strip() else '',
            'model': model.strip(),
        },
        request=http_request,
    )
    return result


@router.post('/admin/providers/{provider}/test')
async def admin_test_provider(
    provider: str,
    http_request: Request,
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """连通性测试：DeepSeek 先查余额再发极小消息，其余平台发最小请求。"""
    from app.services.audit import record_audit
    from app.services.provider_status import test_provider

    result = await test_provider(provider)
    await record_audit(
        db,
        user=admin_user,
        action='test_provider',
        target_type='provider',
        target_id=provider,
        detail={'ok': bool(result.get('ok')), 'detail': str(result.get('detail', ''))[:200]},
        request=http_request,
    )
    return result


@router.post('/admin/providers/refresh-balance')
async def admin_refresh_provider_balance(
    _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict:
    """手动刷新 DeepSeek 余额缓存。"""
    from app.services.provider_status import refresh_deepseek_balance

    return await refresh_deepseek_balance(db)


@router.post('/admin/announcements')
async def admin_send_announcement(
    http_request: Request,
    title: str = Body(..., embed=True),
    body: str = Body(..., embed=True),
    role: str = Body(default='all', embed=True),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import record_audit

    if not title.strip() or not body.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='标题与内容不能为空')
    if role not in {'all', 'student', 'teacher'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='目标角色非法')
    sent = await admin_service.send_announcement(db, title=title.strip(), body=body.strip(), role=role)
    await record_audit(
        db,
        user=admin_user,
        action='send_announcement',
        target_type='notification',
        detail={'title': title.strip()[:80], 'role': role, 'sent': sent},
        request=http_request,
    )
    return {'ok': True, 'sent': sent}


@router.get('/admin/export/{kind}')
async def admin_export_csv(
    kind: str,
    days: int = 30,
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from urllib.parse import quote

    result = await admin_service.export_csv(db, kind, days=days)
    if result is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='不支持的导出类型')
    filename, content = result
    return StreamingResponse(
        iter([content]),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get('/admin/files')
async def admin_list_files(_: object = Depends(require_admin)) -> dict:
    return admin_service.list_upload_files()


@router.delete('/admin/files')
async def admin_delete_file(
    http_request: Request,
    path: str,
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import record_audit

    ok = admin_service.delete_upload_file(path)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='文件不存在或路径非法')
    await record_audit(
        db, user=admin_user, action='delete_file', target_type='file', target_id=path, request=http_request
    )
    return {'ok': True, 'path': path}


@router.post('/admin/users/{user_id}/reset-password')
async def admin_reset_user_password(
    user_id: str,
    http_request: Request,
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import record_audit

    result = await admin_service.reset_user_password(db, user_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在')
    item, temp_password = result
    await record_audit(
        db,
        user=admin_user,
        action='reset_password',
        target_type='user',
        target_id=item.username,
        request=http_request,
    )
    return {'ok': True, 'user': item.model_dump(), 'temp_password': temp_password}


@router.post('/admin/users/batch-active')
async def admin_batch_active(
    http_request: Request,
    user_ids: list[str] = Body(..., embed=True),
    is_active: bool = Body(..., embed=True),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import record_audit

    count = await admin_service.batch_set_active(db, user_ids, is_active)
    await record_audit(
        db,
        user=admin_user,
        action='batch_set_active',
        target_type='user',
        detail={'count': count, 'is_active': is_active},
        request=http_request,
    )
    return {'ok': True, 'updated': count}


@router.get('/admin/users/{user_id}/detail')
async def admin_user_detail(
    user_id: str, _: object = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> dict:
    detail = await admin_service.user_admin_detail(db, user_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='用户不存在')
    return detail


@router.get('/admin/feedback')
async def admin_list_feedback(
    status_filter: str = '',
    category: str = '',
    limit: int = 100,
    _: object = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.feedback import list_feedback

    return await list_feedback(db, status=status_filter, category=category, limit=limit)


@router.patch('/admin/feedback/{feedback_id}')
async def admin_update_feedback(
    feedback_id: str,
    http_request: Request,
    new_status: str | None = Body(default=None, embed=True, alias='status'),
    reply: str | None = Body(default=None, embed=True),
    admin_user=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.audit import record_audit
    from app.services.feedback import update_feedback

    result = await update_feedback(db, feedback_id, status=new_status, reply=reply)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='反馈不存在')
    await record_audit(
        db,
        user=admin_user,
        action='update_feedback',
        target_type='feedback',
        target_id=feedback_id,
        detail={'status': new_status or '', 'replied': bool(reply)},
        request=http_request,
    )
    return result


# ----------------------------- 用户反馈（学生 / 教师提交） -----------------------------
@router.post('/feedback')
async def create_user_feedback(
    category: str = Body(default='suggestion', embed=True),
    content: str = Body(..., embed=True),
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.feedback import create_feedback

    if not content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='反馈内容不能为空')
    return await create_feedback(db, current_user, category=category, content=content)


@router.get('/feedback/mine')
async def my_feedback(
    current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)
) -> list[dict]:
    from app.services.feedback import list_my_feedback

    return await list_my_feedback(db, current_user.id)


# ----------------------------- 聊天区（班级群聊 / 私聊） -----------------------------
@router.get('/chat/rooms', response_model=list[ChatRoomOut])
async def chat_rooms(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[ChatRoomOut]:
    if current_user.role == "student" and current_user.class_id:
        await ensure_class_room_for_student(db, current_user)
    rows = await list_user_rooms(db, current_user.id)
    return [ChatRoomOut(**row) for row in rows]


@router.get('/chat/rooms/{room_id}/messages', response_model=list[ChatRoomMessageOut])
async def chat_room_messages(
    room_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatRoomMessageOut]:
    rows = await list_room_messages(db, room_id, current_user.id)
    return [ChatRoomMessageOut(**row) for row in rows]


@router.post('/chat/rooms/{room_id}/messages', response_model=ChatRoomMessageOut)
async def chat_send_message(
    room_id: str,
    request: ChatSendRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatRoomMessageOut:
    msg = await send_room_message(db, room_id, current_user.id, request.content)
    if msg is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权发送消息')
    return ChatRoomMessageOut(**msg)


@router.post('/chat/private', response_model=ChatRoomOut)
async def chat_create_private(
    request: PrivateChatCreateRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatRoomOut:
    room = await create_private_room(db, current_user.id, request.target_user_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法创建私聊')
    return ChatRoomOut(
        id=room.id,
        room_type=room.room_type,
        title=room.title,
        class_id=room.class_id,
        created_by=room.created_by,
    )


@router.get('/chat/classmates', response_model=list[TeacherBrief])
async def chat_classmates(current_user=Depends(require_current_user), db: AsyncSession = Depends(get_db)) -> list[TeacherBrief]:
    rows = await list_classmates(db, current_user)
    return [TeacherBrief(id=u.id, username=u.username, display_name=u.display_name) for u in rows]


@router.post('/chat/topics', response_model=ChatRoomOut)
async def chat_create_topic(
    request: TopicRoomCreateIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatRoomOut:
    room = await create_topic_room(db, current_user, request.title)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法创建话题频道')
    return ChatRoomOut(
        id=room.id,
        room_type=room.room_type,
        title=room.title,
        class_id=room.class_id,
        created_by=room.created_by,
    )


@router.delete('/chat/topics/{room_id}')
async def chat_delete_topic(
    room_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await delete_topic_room(db, current_user, room_id)
    if result == "not_found":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='话题频道不存在')
    if result == "forbidden":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='仅创建者可删除话题频道')
    return {"ok": True}


@router.post('/chat/messages/{message_id}/reactions', response_model=list[ChatReactionOut])
async def chat_toggle_reaction(
    message_id: str,
    request: ChatReactionIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatReactionOut]:
    rows = await toggle_message_reaction(db, current_user.id, message_id, request.emoji)
    return [ChatReactionOut(message_id=message_id, **r) for r in rows]


@router.get('/chat/rooms/{room_id}/summary', response_model=ChatSummaryOut)
async def chat_room_summary(
    room_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSummaryOut:
    data = await summarize_room_today(db, room_id, current_user.id)
    return ChatSummaryOut(**data)


@router.post('/chat/groups', response_model=ChatRoomOut)
async def chat_create_group(
    request: GroupChatCreateIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatRoomOut:
    room = await create_group_room(db, current_user, request.title, request.member_ids)
    if room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='无法创建群聊')
    return ChatRoomOut(
        id=room.id,
        room_type=room.room_type,
        title=room.title,
        class_id=room.class_id,
        created_by=room.created_by,
    )


@router.post('/chat/groups/{room_id}/invite')
async def chat_invite_group(
    room_id: str,
    request: GroupInviteIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await invite_to_group(db, current_user, room_id, request.target_user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='邀请失败')
    return {'ok': True}


# ----------------------------- AI 学习工具 -----------------------------
@router.post('/ai/similar', response_model=SimilarQuestionsResponse)
async def ai_similar(
    request: SimilarQuestionsRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> SimilarQuestionsResponse:
    return await generate_similar_questions(db, current_user, request)


@router.post('/ai/grade', response_model=GradeResponse)
async def ai_grade(
    request: GradeRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> GradeResponse:
    return await grade_answers(db, current_user, request)


# ----------------------------- 桌宠 -----------------------------
@router.get('/pets', response_model=list[PetManifestOut])
async def pets() -> list[PetManifestOut]:
    return list_pet_manifests()


@router.get('/pets/owned')
async def pets_owned(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    owned = await list_owned_pet_slugs(db, current_user)
    return {"owned": sorted(owned)}


@router.post('/users/me/pet', response_model=UserInfo)
async def select_pet(
    request: PetSelectRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    try:
        user = await set_user_pet(db, current_user, request.pet_slug)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return user_to_info(user)


@router.post('/pets/affinity', response_model=PetAffinityOut)
async def pet_affinity_bump(
    request: PetAffinityIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> PetAffinityOut:
    data = await bump_pet_affinity(db, current_user, request.delta)
    return PetAffinityOut(**data)


@router.get('/pets/affinity', response_model=PetAffinityOut)
async def pet_affinity_get(current_user=Depends(require_current_user)) -> PetAffinityOut:
    level, name = affinity_level(int(current_user.pet_affinity or 0))
    return PetAffinityOut(pet_affinity=int(current_user.pet_affinity or 0), level=level, level_name=name)


@router.post('/users/me/title', response_model=UserInfo)
async def equip_title(
    request: EquippedTitleIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    try:
        user = await set_equipped_title(db, current_user, request.title_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return user_to_info(user)


@router.post('/users/me/study-theme', response_model=UserInfo)
async def equip_study_theme(
    request: StudyThemeIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserInfo:
    user = await set_study_theme(db, current_user, request.theme_id)
    return user_to_info(user)


# ----------------------------- 自习区 -----------------------------
@router.get('/study/constellations', response_model=list[StudyConstellationOut])
async def study_constellations(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudyConstellationOut]:
    rows = await study_list_constellations(db)
    return [StudyConstellationOut(**row) for row in rows]


@router.get('/study/rooms', response_model=list[StudyRoomOut])
async def study_rooms(
    constellation: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudyRoomOut]:
    rows = await study_list_rooms(db, constellation)
    return [StudyRoomOut(**row) for row in rows]


@router.post('/study/rooms/{room_id}/join', response_model=StudyJoinResponse)
async def study_join(
    room_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyJoinResponse:
    try:
        room, occupants = await study_join_room(db, current_user, room_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return StudyJoinResponse(
        room=StudyRoomOut(**room),
        occupants=[OccupantOut(**o) for o in occupants],
    )


@router.post('/study/rooms/{room_id}/leave')
async def study_leave(
    room_id: str,
    current_user=Depends(require_current_user),
) -> dict[str, str]:
    current = get_user_study_room(current_user.id)
    if current == room_id:
        await study_leave_room(current_user.id)
    return {'status': 'ok'}


@router.get('/study/rooms/{room_id}/occupants', response_model=list[OccupantOut])
async def study_occupants(
    room_id: str,
    current_user=Depends(require_current_user),
) -> list[OccupantOut]:
    return [OccupantOut(**o) for o in study_list_occupants(room_id)]


@router.post('/study/rooms/{room_id}/status')
async def study_update_status(
    room_id: str,
    payload: dict,
    current_user=Depends(require_current_user),
) -> dict[str, str]:
    status = str(payload.get('status', 'focus'))
    current = get_user_study_room(current_user.id)
    if current != room_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='未在该自习室')
    await update_occupant_status(current_user.id, status)
    return {'status': 'ok'}


@router.get('/study/rooms/{room_id}/pomodoro')
async def study_room_pomodoro_state(
    room_id: str,
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    from app.services.study_service import get_room_pomodoro

    state = get_room_pomodoro(room_id)
    return {'active': state is not None, **(state or {})}


@router.post('/study/rooms/{room_id}/pomodoro')
async def study_room_pomodoro(
    room_id: str,
    payload: dict,
    current_user=Depends(require_current_user),
) -> dict:
    """集体番茄钟：action=start|stop，start 需带 minutes。"""
    from app.services.study_service import start_room_pomodoro, stop_room_pomodoro

    if get_user_study_room(current_user.id) != room_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='未在该自习室')
    action = str(payload.get('action') or 'start')
    try:
        if action == 'stop':
            return await stop_room_pomodoro(current_user)
        state = await start_room_pomodoro(current_user, int(payload.get('minutes') or 25))
        return {'ok': True, **state}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/study/invite-buddy')
async def study_invite_buddy(
    payload: dict,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """邀请同学来自习室共学（发通知）。未入座时发软邀请，引导对方进入自习区。"""
    from app.services.notification_service import create_notification
    from app.services.study_service import get_room

    buddy_id = str(payload.get('buddy_id') or '').strip()
    if not buddy_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='缺少 buddy_id')
    if buddy_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='不能邀请自己')
    room_id = get_user_study_room(current_user.id)
    inviter = current_user.display_name or current_user.username
    room_name = ''
    if room_id:
        room = await get_room(db, room_id)
        room_name = room.name if room else '自习室'
        body = f'{inviter} 邀请你到「{room_name}」一起自习，去自习区找 TA 吧！'
    else:
        body = f'{inviter} 邀请你一起去自习区共学，打开自习区即可加入！'
    await create_notification(
        db,
        user_id=buddy_id,
        title='共学邀请',
        body=body,
        kind='study_invite',
        link='/student',
    )
    return {'ok': True, 'room_name': room_name}


@router.get('/study/class-presence')
async def study_class_presence(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_teacher_study_presence(db, current_user.id)


@router.post('/study/supervision-event')
async def study_supervision_event(
    payload: dict,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.study_service import create_supervision_alert

    kind = str(payload.get('kind') or '')
    message = str(payload.get('message') or '').strip()
    room_id = str(payload.get('room_id') or '')
    try:
        return await create_supervision_alert(db, current_user, kind, message, room_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/study/supervision-frame')
async def study_supervision_frame(
    file: UploadFile = File(...),
    current_user=Depends(require_current_user),
) -> dict:
    from app.services.study_service import save_supervision_frame

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail='空图片')
    if len(data) > 800_000:
        raise HTTPException(status_code=400, detail='截图过大')
    return await save_supervision_frame(current_user, data)


@router.delete('/study/supervision-frame')
async def study_clear_supervision_frame(
    current_user=Depends(require_current_user),
) -> dict:
    from app.services.study_service import clear_supervision_frame

    clear_supervision_frame(current_user.id)
    return {'ok': True}


@router.get('/teacher/patrol')
async def teacher_patrol(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    from app.services.study_service import list_supervision_patrol

    return await list_supervision_patrol(db, current_user, class_id=class_id)


# ----------------------------- 专注 / 错题 / 星愿 / 商城 / 成就 -----------------------------
@router.post('/focus/session', response_model=FocusSummaryOut)
async def post_focus_session(
    request: FocusSessionIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSummaryOut:
    await create_focus_session(db, current_user, request.minutes, request.source, request.room_id)
    return FocusSummaryOut(**(await focus_summary(db, current_user.id)))


@router.get('/focus/summary', response_model=FocusSummaryOut)
async def get_focus_summary(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusSummaryOut:
    return FocusSummaryOut(**(await focus_summary(db, current_user.id)))


@router.get('/focus/heatmap', response_model=FocusHeatmapOut)
async def get_focus_heatmap(
    week_offset: int = 0,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusHeatmapOut:
    return FocusHeatmapOut(**(await focus_heatmap(db, current_user.id, week_offset)))


@router.get('/focus/leaderboard', response_model=list[FocusLeaderboardItem])
async def get_focus_leaderboard(
    room_id: str = '',
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[FocusLeaderboardItem]:
    rows = await focus_leaderboard(db, room_id=room_id or '')
    return [FocusLeaderboardItem(**r) for r in rows]


@router.get('/mistakes', response_model=list[MistakeOut])
async def get_mistakes(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MistakeOut]:
    rows = await list_mistakes(db, current_user.id)
    return [
        MistakeOut(
            id=r.id,
            question=r.question,
            student_answer=r.student_answer,
            correct_answer=r.correct_answer,
            subject=r.subject,
            note=r.note,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.post('/mistakes', response_model=MistakeOut)
async def post_mistake(
    request: MistakeIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> MistakeOut:
    row = await add_mistake(db, current_user, request.model_dump())
    try:
        await record_learning_event(
            db,
            current_user.id,
            'mistake_added',
            f"错题登记：{(request.question or '')[:80]}",
            {'subject': request.subject},
        )
    except Exception:
        pass
    return MistakeOut(
        id=row.id,
        question=row.question,
        student_answer=row.student_answer,
        correct_answer=row.correct_answer,
        subject=row.subject,
        note=row.note,
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


@router.delete('/mistakes/{mistake_id}')
async def remove_mistake(
    mistake_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    ok = await delete_mistake(db, current_user.id, mistake_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='错题不存在')
    return {'status': 'ok'}


@router.get('/wishes', response_model=list[WishOut])
async def get_wishes(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WishOut]:
    return [WishOut(**w) for w in await list_wishes(db, current_user.id)]


@router.post('/wishes', response_model=WishOut)
async def post_wish(
    request: WishIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> WishOut:
    return WishOut(**(await create_wish(db, current_user, request.content)))


@router.post('/wishes/{wish_id}/like', response_model=WishOut)
async def post_wish_like(
    wish_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> WishOut:
    wish = await like_wish(db, current_user.id, wish_id)
    if wish is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='心愿不存在')
    return WishOut(
        id=wish.id,
        user_id=wish.user_id,
        display_name=wish.display_name,
        content=wish.content,
        likes=wish.likes,
        liked_by_me=True,
        created_at=wish.created_at.isoformat() if wish.created_at else "",
    )


@router.get('/forum/posts', response_model=list[ForumPostOut])
async def get_forum_posts(
    class_id: str = '',
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ForumPostOut]:
    cid = (class_id or current_user.class_id or '').strip()
    return [ForumPostOut(**p) for p in await list_forum_posts(db, class_id=cid)]


@router.post('/forum/posts', response_model=ForumPostOut)
async def post_forum_post(
    request: ForumPostIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ForumPostOut:
    return ForumPostOut(**(await create_forum_post(
        db,
        current_user,
        request.title,
        request.body,
        request.kind,
        request.file_url,
        request.source_type or "",
        request.source_id or "",
    )))


@router.get('/forum/attachable')
async def get_forum_attachable(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.resource_forum import list_attachable as list_forum_attachable
    items = await list_forum_attachable(db, current_user)
    return {"items": items}


@router.post('/forum/posts/{post_id}/like', response_model=ForumPostOut)
async def post_forum_like(
    post_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ForumPostOut:
    post = await like_forum_post(db, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='帖子不存在')
    return ForumPostOut(**post)


@router.post('/forum/posts/{post_id}/promote', response_model=ForumPromoteOut)
async def post_forum_promote(
    post_id: str,
    request: ForumPromoteIn,
    current_user=Depends(require_teacher_or_admin),
    db: AsyncSession = Depends(get_db),
) -> ForumPromoteOut:
    try:
        return ForumPromoteOut(**(await promote_forum_post(
            db, current_user, post_id, request.galaxy_slug, request.planet_slug
        )))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/shop/items', response_model=list[ShopItemOut])
async def shop_items(current_user=Depends(require_current_user)) -> list[ShopItemOut]:
    return [ShopItemOut(**i) for i in await list_shop_items()]


@router.post('/shop/redeem')
async def shop_redeem(
    request: RedeemIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await redeem_item(db, current_user, request.item_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/shop/owned', response_model=list[OwnedShopItemOut])
async def shop_owned(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OwnedShopItemOut]:
    rows = await list_shop_owned(db, current_user.id)
    return [OwnedShopItemOut(**r) for r in rows]


@router.post('/leisure/session', response_model=LeisureSessionOut)
async def leisure_session(
    request: LeisureSessionIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> LeisureSessionOut:
    data = await record_leisure_session(db, current_user, request.game, request.score, request.won)
    return LeisureSessionOut(**data)


@router.post('/mistakes/ocr')
async def mistakes_ocr(
    photo: UploadFile = File(...),
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    data = await photo.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='图片为空')
    from app.services.ark_vision import ark_vision_available

    result = await ocr_mistake_from_image(data, photo.content_type or 'image/jpeg')
    vision_unavailable = not ark_vision_available()
    return {
        'question': result.get('question', ''),
        'subject_guess': result.get('subject', ''),
        'correct_answer_guess': result.get('correct_answer', ''),
        'vision_unavailable': vision_unavailable,
    }


@router.post('/mistakes/import-photo')
async def mistakes_import_photo(
    photo: UploadFile = File(...),
    current_user=Depends(require_current_user),
) -> dict:
    """批量识别一张图中的多道错题，返回预览列表（不入库）。"""
    _ = current_user
    data = await photo.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='图片为空')
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='图片不能超过 10 MB')
    from app.services.zone_extras import ocr_mistakes_batch_from_image

    try:
        items = await ocr_mistakes_batch_from_image(data, photo.content_type or 'image/jpeg')
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {'ok': True, 'items': items}


@router.post('/mistakes/batch', response_model=list[MistakeOut])
async def post_mistakes_batch(
    request: list[MistakeIn],
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MistakeOut]:
    """批量入库（拍照导入确认后调用）。"""
    if len(request) > 20:
        raise HTTPException(status_code=422, detail='一次最多导入 20 道错题')
    out: list[MistakeOut] = []
    for item in request:
        row = await add_mistake(db, current_user, item.model_dump())
        out.append(
            MistakeOut(
                id=row.id,
                question=row.question,
                student_answer=row.student_answer,
                correct_answer=row.correct_answer,
                subject=row.subject,
                note=row.note,
                created_at=row.created_at.isoformat() if row.created_at else "",
            )
        )
    try:
        await record_learning_event(
            db,
            current_user.id,
            'mistake_added',
            f"拍照批量导入错题 {len(out)} 道",
            {'count': len(out)},
        )
    except Exception:
        pass
    return out


@router.get('/achievements', response_model=list[AchievementOut])
async def achievements(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AchievementOut]:
    return [AchievementOut(**a) for a in await list_achievements(db, current_user)]


@router.get('/achievements/milestones', response_model=list[MilestoneOut])
async def achievement_milestones(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MilestoneOut]:
    return [MilestoneOut(**m) for m in await list_milestones(db, current_user.id)]


@router.get('/learn/daily-tasks', response_model=list[DailyTaskOut])
async def get_daily_tasks(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DailyTaskOut]:
    rows = await ensure_daily_tasks(db, current_user)
    return [DailyTaskOut(**r) for r in rows]


@router.post('/learn/daily-tasks/toggle', response_model=DailyTaskOut)
async def toggle_daily_task_route(
    request: DailyTaskToggleIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> DailyTaskOut:
    row = await toggle_daily_task(db, current_user, request.task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='任务不存在')
    return DailyTaskOut(**row)


@router.get('/learn/knowledge-graph', response_model=KnowledgeGraphOut)
async def get_knowledge_graph(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeGraphOut:
    data = await knowledge_graph(db, current_user.id)
    return KnowledgeGraphOut(**data)


@router.get('/learn/buddy-matches', response_model=list[BuddyMatchOut])
async def get_buddy_matches(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BuddyMatchOut]:
    rows = await buddy_matches(db, current_user)
    return [BuddyMatchOut(**r) for r in rows]


@router.get('/learn/progress-board', response_model=ProgressBoardOut)
async def get_progress_board(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProgressBoardOut:
    data = await progress_board(db, current_user)
    return ProgressBoardOut(**data)


@router.get('/leisure/sign-in', response_model=SignInOut)
async def leisure_sign_in_status(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> SignInOut:
    data = await fetch_sign_in_status(db, current_user.id)
    return SignInOut(**data)


@router.post('/leisure/sign-in', response_model=SignInOut)
async def leisure_sign_in(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> SignInOut:
    data = await sign_in_today(db, current_user)
    return SignInOut(**data)


@router.get('/study/streak-calendar', response_model=StudyStreakOut)
async def study_streak(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudyStreakOut:
    data = await study_streak_calendar(db, current_user.id)
    return StudyStreakOut(**data)


@router.post('/leisure/challenges', response_model=GameChallengeOut)
async def create_challenge(
    request: GameChallengeIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> GameChallengeOut:
    try:
        data = await create_game_challenge(db, current_user, request.target_user_id, request.game, request.score)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GameChallengeOut(**data)


@router.post('/leisure/challenges/{challenge_id}/respond', response_model=GameChallengeOut)
async def respond_challenge(
    challenge_id: str,
    request: GameChallengeIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> GameChallengeOut:
    try:
        data = await respond_game_challenge(db, current_user, challenge_id, request.score)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return GameChallengeOut(**data)


@router.get('/leisure/challenges/pending', response_model=list[GameChallengeOut])
async def pending_challenges(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GameChallengeOut]:
    rows = await list_pending_challenges(db, current_user.id)
    return [GameChallengeOut(**r) for r in rows]


@router.get('/learn/knowledge/{slug}/explain', response_model=KnowledgeExplainOut)
async def explain_knowledge(
    slug: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeExplainOut:
    data = await explain_knowledge_node(db, current_user.id, slug)
    return KnowledgeExplainOut(**data)


@router.post('/learn/knowledge/ask', response_model=KnowledgeAskOut)
async def ask_knowledge_api(
    request: KnowledgeAskIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeAskOut:
    data = await ask_knowledge(db, current_user.id, request.slug, request.question)
    return KnowledgeAskOut(**data)


@router.get('/learn/ai-quiz/{slug}', response_model=AiQuizOut)
async def ai_quiz_api(
    slug: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiQuizOut:
    data = await generate_ai_quiz(db, current_user.id, slug)
    return AiQuizOut(**data)


@router.post('/learn/ai-quiz/submit', response_model=AiQuizSubmitOut)
async def ai_quiz_submit_api(
    request: AiQuizSubmitRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> AiQuizSubmitOut:
    data = await submit_ai_quiz(
        db,
        current_user.id,
        slug=request.slug,
        question_index=request.question_index,
        answer=request.answer,
        self_ok=request.self_ok,
    )
    return AiQuizSubmitOut(**data)


@router.get('/focus/yearly', response_model=FocusYearlyOut)
async def focus_yearly(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> FocusYearlyOut:
    data = await focus_yearly_calendar(db, current_user.id)
    return FocusYearlyOut(**data)


@router.get('/notifications', response_model=list[NotificationOut])
async def get_notifications(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NotificationOut]:
    rows = await list_notifications(db, current_user.id)
    return [NotificationOut(**r) for r in rows]


@router.get('/notifications/unread-count')
async def get_unread_notification_count(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await unread_count(db, current_user.id)
    return {'count': count}


@router.post('/notifications/{notification_id}/read')
async def read_notification(
    notification_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await mark_read(db, current_user.id, notification_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='通知不存在')
    return {'ok': True}


@router.post('/notifications/read-all')
async def read_all_notifications(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await mark_all_read(db, current_user.id)
    return {'ok': True}


@router.get('/tree-hole/diaries', response_model=list[MoodDiaryOut])
async def tree_hole_diaries(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MoodDiaryOut]:
    rows = await list_diaries(db, current_user.id)
    return [MoodDiaryOut(**r) for r in rows]


@router.post('/tree-hole/diaries', response_model=MoodDiaryOut)
async def tree_hole_create_diary(
    request: MoodDiaryIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> MoodDiaryOut:
    row = await create_diary(db, current_user.id, request.mood, request.content, request.image_url)
    return MoodDiaryOut(**row)


@router.get('/tree-hole/posts', response_model=list[TreeHolePostOut])
async def tree_hole_posts(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TreeHolePostOut]:
    rows = await list_posts(db, current_user.id)
    return [TreeHolePostOut(**r) for r in rows]


@router.post('/tree-hole/posts', response_model=TreeHolePostOut)
async def tree_hole_create_post(
    request: TreeHolePostIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> TreeHolePostOut:
    row = await create_post(db, current_user.id, request.content, request.image_url)
    return TreeHolePostOut(**row)


@router.delete('/tree-hole/posts/{post_id}')
async def tree_hole_delete_post(
    post_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not await delete_post(db, current_user.id, post_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='帖子不存在或无权撤销')
    return {'ok': True}


@router.post('/tree-hole/posts/{post_id}/like')
async def tree_hole_like_post(
    post_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await toggle_like(db, current_user.id, post_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post('/tree-hole/posts/{post_id}/react')
async def tree_hole_react_post(
    post_id: str,
    request: TreeHoleReactIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await react_post(db, current_user.id, post_id, request.emoji)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/tree-hole/posts/{post_id}/comments', response_model=list[TreeHoleCommentOut])
async def tree_hole_list_comments(
    post_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TreeHoleCommentOut]:
    try:
        rows = await list_comments(db, post_id)
        return [TreeHoleCommentOut(**r) for r in rows]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post('/tree-hole/posts/{post_id}/comments', response_model=TreeHoleCommentOut)
async def tree_hole_create_comment(
    post_id: str,
    request: TreeHoleCommentIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> TreeHoleCommentOut:
    try:
        row = await create_comment(db, current_user.id, post_id, request.content, request.emoji)
        return TreeHoleCommentOut(**row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/tree-hole/upload-image')
async def tree_hole_upload_image(
    image: UploadFile = File(...),
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    try:
        url = await save_upload_file(image, TREEHOLE_DIR, 'treehole')
        return {'url': url}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/notes', response_model=list[NoteOut])
async def notes_list(
    planet_slug: str = '',
    galaxy_slug: str = '',
    q: str = '',
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[NoteOut]:
    rows = await list_notes(
        db, current_user.id, planet_slug=planet_slug, galaxy_slug=galaxy_slug, q=q
    )
    return [NoteOut(**r) for r in rows]


@router.post('/notes', response_model=NoteOut)
async def notes_create(
    request: NoteIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    row = await create_note(
        db,
        current_user.id,
        title=request.title,
        content=request.content,
        planet_slug=request.planet_slug,
        galaxy_slug=request.galaxy_slug,
        attachment_url=request.attachment_url,
        blocks_json=request.blocks_json,
        source=request.source,
        session_id=request.session_id,
    )
    return NoteOut(**row)


@router.patch('/notes/{note_id}', response_model=NoteOut)
async def notes_update(
    note_id: str,
    request: NoteUpdateIn,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> NoteOut:
    row = await update_note(
        db,
        current_user.id,
        note_id,
        title=request.title,
        content=request.content,
        blocks_json=request.blocks_json,
        attachment_url=request.attachment_url,
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='笔记不存在')
    return NoteOut(**row)


@router.delete('/notes/{note_id}')
async def notes_delete(
    note_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await delete_note(db, current_user.id, note_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='笔记不存在')
    return {'ok': True}


@router.post('/notes/upload')
async def notes_upload_attachment(
    file: UploadFile = File(...),
    current_user=Depends(require_current_user),
) -> dict:
    _ = current_user
    try:
        url = await save_upload_file(file, NOTES_DIR, 'notes')
        return {'url': url}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/teacher/resources', response_model=LessonResourceOut)
async def teacher_upload_resource(
    title: str = Form(''),
    galaxy_slug: str = Form(''),
    class_id: str = Form(''),
    resource_kind: str = Form('other'),
    file: UploadFile = File(...),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> LessonResourceOut:
    try:
        file_url = await save_upload_file(file, RESOURCES_DIR, 'resources')
        row = await create_lesson_resource(
            db,
            current_user,
            title=title,
            galaxy_slug=galaxy_slug,
            file_url=file_url,
            class_id=class_id,
            resource_kind=resource_kind,
        )
        return LessonResourceOut(**row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/teacher/resources/from-text', response_model=LessonResourceOut)
async def teacher_resource_from_text(
    body: LessonResourceTextIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> LessonResourceOut:
    try:
        row = await create_lesson_resource_from_text(
            db,
            current_user,
            title=body.title,
            content=body.content,
            galaxy_slug=body.galaxy_slug,
            class_id=body.class_id,
            resource_kind=body.resource_kind,
        )
        return LessonResourceOut(**row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/teacher/resources/{resource_id}/promote-to-starlib')
async def teacher_promote_resource(
    resource_id: str,
    body: PromoteResourceIn = Body(default=PromoteResourceIn()),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await promote_lesson_resource_to_starlib(
            db,
            current_user,
            resource_id,
            class_id=body.class_id,
            galaxy_slug=body.galaxy_slug,
            planet_slug=body.planet_slug,
            asset_type=body.asset_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/teacher/generated/{resource_id}/promote-to-starlib')
async def teacher_promote_generated(
    resource_id: str,
    body: PromoteResourceIn = Body(default=PromoteResourceIn()),
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await promote_generated_to_starlib(
            db,
            current_user,
            resource_id,
            class_id=body.class_id,
            galaxy_slug=body.galaxy_slug,
            planet_slug=body.planet_slug,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete('/teacher/resources/{resource_id}')
async def teacher_delete_resource(
    resource_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ok = await delete_lesson_resource(db, current_user, resource_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='资料不存在')
    return {'ok': True}


@router.get('/resources', response_model=list[LessonResourceOut])
async def resources_list(
    galaxy_slug: str = '',
    resource_kind: str = '',
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LessonResourceOut]:
    rows = await list_lesson_resources(
        db, current_user, galaxy_slug=galaxy_slug, resource_kind=resource_kind
    )
    return [LessonResourceOut(**r) for r in rows]


# ----------------------------- 会话（旧占位保留兼容） -----------------------------
@router.post('/chats/sessions', response_model=ChatSessionOut)
async def create_chat_session(request: ChatSessionCreate) -> ChatSessionOut:
    return ChatSessionOut(id='session-demo-001', user_id=request.user_id, title=request.title, status='active')


@router.post('/chats/messages', response_model=ChatMessageOut)
async def create_chat_message(request: ChatMessageCreate) -> ChatMessageOut:
    return ChatMessageOut(
        id='message-demo-001',
        session_id=request.session_id,
        user_id=request.user_id,
        role=request.role,
        content=request.content,
    )


@router.get('/profiles/timeline', response_model=list[ProfileTimelineItem])
async def profile_timeline(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProfileTimelineItem]:
    return await list_profile_timeline(db, user_id=current_user.id)


@router.post('/profiles/refresh')
async def profile_refresh_manual(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    row = await refresh_profile_from_events(db, current_user.id)
    if row is None:
        return {'ok': False, 'message': '暂无待处理的学习行为事件', 'status': 'already_fresh'}
    return {'ok': True, 'profile_id': row.id, 'message': '画像已随学随新更新', 'status': 'refreshed'}


@router.get('/profiles/evidence')
async def profile_evidence(
    dimension: str = '',
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.profile_refresh import list_dimension_evidence
    return await list_dimension_evidence(db, current_user.id, dimension=dimension)


# ----------------------------- 多智能体资源生成 -----------------------------
@router.get('/resources/deck-templates')
async def resources_deck_templates(current_user=Depends(require_current_user)) -> dict:
    _ = current_user
    from app.services.deck_themes import list_deck_templates

    return {"templates": list_deck_templates()}


@router.post('/resources/generate', response_model=ResourceGenerateResponse)
async def resources_generate(
    request: ResourceGenerateRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResourceGenerateResponse:
    run_id = f'res-{uuid.uuid4().hex[:10]}'
    register_resource_run(run_id, {
        'user_id': current_user.id,
        'planet_slug': request.planet_slug,
        'kinds': request.kinds,
        'extra': request.extra_requirements,
        'quiz_types': list(request.quiz_types or []),
        'deck_template': request.deck_template or 'orbit',
    })
    return ResourceGenerateResponse(run_id=run_id, status='running')


@router.get('/resources/generate/{run_id}/stream')
async def resources_generate_stream(
    run_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    params = get_resource_run(run_id)
    if params is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='生成任务不存在或已过期',
        )
    if params.get('user_id') != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权访问该生成任务')

    async def event_stream():
        async for event in run_resource_generation(
            db,
            current_user,
            params.get('planet_slug') or '',
            params.get('kinds') or ['doc'],
            params.get('extra') or '',
            quiz_types=params.get('quiz_types') or [],
            run_id=run_id,
            deck_template=params.get('deck_template') or 'orbit',
        ):
            yield format_resource_sse(event)

    return StreamingResponse(event_stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.get('/learn/resources', response_model=list[GeneratedResourceOut])
async def learn_resources_list(
    planet_slug: str = '',
    kind: str = '',
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GeneratedResourceOut]:
    rows = await list_user_resources(db, current_user.id, planet_slug=planet_slug, kind=kind)
    return [GeneratedResourceOut(**r) for r in rows]


@router.get('/learn/resources/{resource_id}', response_model=GeneratedResourceOut)
async def learn_resource_detail(
    resource_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> GeneratedResourceOut:
    row = await get_resource(db, current_user.id, resource_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='资源不存在')
    return GeneratedResourceOut(**row)


# ----------------------------- 学习路径与推荐 -----------------------------
@router.post('/learn/path/generate', response_model=LearningPathOut)
async def learn_path_generate(
    request: LearningPathGenerateRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearningPathOut:
    hints: list[str] = []
    if request.use_evaluation:
        report = await build_evaluation_report(db, current_user)
        hints = evaluation_suggestions_for_path(report)
    return await generate_learning_path(db, current_user, goal=request.goal, evaluation_hints=hints)


@router.get('/learn/path')
async def learn_path_current(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_active_path(db, current_user.id)


@router.post('/learn/path/steps/{step_index}/complete', response_model=LearningPathOut)
async def learn_path_complete_step(
    step_index: int,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearningPathOut:
    try:
        return await complete_path_step(db, current_user.id, step_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/learn/path/steps/{step_index}/mount', response_model=LearningPathOut)
async def learn_path_mount_step(
    step_index: int,
    body: PathMountRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearningPathOut:
    try:
        return await mount_path_step(
            db,
            current_user.id,
            step_index,
            kind=body.kind,
            item_id=body.id,
            title=body.title,
            reason=body.reason,
            unmount=body.unmount,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/learn/sprint/generate', response_model=LearningPathOut)
async def learn_sprint_generate(
    payload: dict,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearningPathOut:
    """考试冲刺模式：按天倒排的冲刺计划。"""
    from app.services.learning_path import generate_sprint_path

    try:
        return await generate_sprint_path(
            db,
            current_user,
            exam_name=str(payload.get('exam_name') or '')[:64],
            exam_date=str(payload.get('exam_date') or ''),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get('/learn/sprint')
async def learn_sprint_current(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.learning_path import get_sprint_path

    return await get_sprint_path(db, current_user.id)


@router.post('/learn/sprint/{path_id}/steps/{step_index}/complete', response_model=LearningPathOut)
async def learn_sprint_complete_step(
    path_id: str,
    step_index: int,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> LearningPathOut:
    from app.services.learning_path import complete_sprint_step

    try:
        return await complete_sprint_step(db, current_user.id, path_id, step_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/learn/recommendations', response_model=list[RecommendationItem])
async def learn_recommendations(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RecommendationItem]:
    return await build_recommendations(db, current_user)


@router.get('/learn/evaluation-report', response_model=EvaluationReportOut)
async def learn_evaluation_report(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluationReportOut:
    return await build_evaluation_report(db, current_user)


@router.post('/learn/evaluation-report/apply-to-path')
async def learn_evaluation_apply_to_path(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
    auto_generate: bool = False,
):
    """评估建议回灌 PathPlanner；auto_generate=true 时走完整闭环。"""
    if auto_generate:
        from app.services.learning_loop import run_eval_path_resource_loop

        return await run_eval_path_resource_loop(db, current_user, auto_generate=True, top_k=2)
    report = await build_evaluation_report(db, current_user)
    hints = evaluation_suggestions_for_path(report)
    return await generate_learning_path(
        db,
        current_user,
        goal="根据成长评估动态调整学习计划",
        evaluation_hints=hints,
    )


@router.post('/learn/closed-loop/run')
async def learn_closed_loop_run(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
    top_k: int = 2,
    auto_generate: bool = True,
) -> dict:
    """一键闭环：评估 → 路径重排 → TopK 弱项资源生成（写 mode=loop AgentRun）。"""
    from app.services.learning_loop import run_eval_path_resource_loop

    return await run_eval_path_resource_loop(
        db,
        current_user,
        auto_generate=auto_generate,
        top_k=top_k,
    )


@router.get('/learn/simulation-calibration')
async def learn_simulation_calibration(
    planet_slug: str = '',
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.calibration import list_calibration

    rows = await list_calibration(db, current_user.id, planet_slug=planet_slug)
    return {"items": rows, "count": len(rows)}


@router.get('/teacher/calibration-summary')
async def teacher_calibration_summary_route(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.calibration import teacher_calibration_summary

    return await teacher_calibration_summary(db, current_user, class_id)


@router.get('/learn/mastery-overview', response_model=MasteryOverviewOut)
async def learn_mastery_overview(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> MasteryOverviewOut:
    return await get_mastery_overview(db, current_user.id)


# ----------------------------- 画像抽取（Profiler Agent） -----------------------------
@router.post('/profiles/extract', response_model=ProfileResponse)
async def extract_profile(
    request: ProfileRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileResponse:
    chat_history = [message.model_dump() for message in request.chat_history]
    try:
        profile = await extract_student_profile(chat_history)
        saved = await save_student_profile(
            db,
            profile.model_copy(update={'student_name': request.student_name or current_user.display_name}),
            user_id=current_user.id,
            apply_floor_merge=True,
        )
        merged = _build_profile_extract(saved)
        merged.summary = saved.summary or profile.summary
        missing = [
            m for m in list(saved.missing_dimensions or []) if m in _DIMENSIONS
        ]
        merged.missing_dimensions = missing  # type: ignore[assignment]
        follow_ups = list(saved.follow_up_questions or profile.follow_up_questions or [])
        merged.follow_up_questions = [str(q) for q in follow_ups if q]
        raw = {
            'missing_dimensions': merged.missing_dimensions,
            'saved_profile_id': saved.id,
            'saved_student_name': saved.student_name,
            'floors': saved.dimension_floors_json or {},
            'warnings': saved.warnings_json or [],
        }
        return ProfileResponse(profile=merged, raw=raw)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception('profile extract failed for user=%s: %s', current_user.id, exc)
        detail = str(exc)
        if 'Unknown column' in detail or 'OperationalError' in type(exc).__name__:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='画像落库失败：数据库表结构与当前版本不一致，请重启后端以自动迁移后重试。',
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'画像抽取失败：{type(exc).__name__}',
        ) from exc


@router.get('/profiles/history', response_model=list[ProfileHistoryItem])
async def profile_history(
    student_name: str | None = None,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProfileHistoryItem]:
    _ = student_name
    return await list_profile_history(db, user_id=current_user.id)


@router.get('/profiles/meta', response_model=ProfileMetaOut)
async def profile_meta(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileMetaOut:
    data = await get_user_profile_meta(db, current_user.id)
    return ProfileMetaOut(**data)


@router.get('/profiles/improvement/plans')
async def improvement_plans(
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_user_plans(db, current_user.id)


@router.patch('/profiles/improvement/plans/{plan_id}/steps/{step_index}')
async def improvement_update_step(
    plan_id: str,
    step_index: int,
    request: PlanStepUpdate,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await update_plan_step(
        db,
        user_id=current_user.id,
        plan_id=plan_id,
        step_index=step_index,
        done=request.done,
        evidence_text=request.evidence_text,
    )


@router.post('/profiles/improvement/plans/{plan_id}/submit')
async def improvement_submit(
    plan_id: str,
    request: ImprovementSubmitRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await submit_improvement(
        db,
        user_id=current_user.id,
        plan_id=plan_id,
        reflection=request.reflection,
    )


@router.post('/profiles/improvement/plans/{plan_id}/sync-to-path')
async def improvement_sync_to_path(
    plan_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    plans = await list_user_plans(db, current_user.id)
    plan = next((p for p in plans if p.get("id") == plan_id), None)
    if plan is None:
        raise HTTPException(status_code=404, detail="未找到补救计划")
    step_titles = [str(s.get("title") or "") for s in (plan.get("steps") or []) if s.get("title")]
    if not step_titles:
        raise HTTPException(status_code=400, detail="补救步骤为空")
    path = await sync_remediation_steps_to_path(
        db,
        current_user,
        topic=str(plan.get("topic") or ""),
        steps=step_titles,
        root_cause=str(plan.get("root_cause") or ""),
        target_dimension=str(plan.get("target_dimension") or ""),
    )
    return {
        "path_id": path.id,
        "title": path.title,
        "steps": len(path.steps),
        "message": "补救步骤已同步到学习路径，可在「学习路径」面板查看",
    }


@router.get('/teacher/improvement/pending')
async def teacher_improvement_pending(
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await list_pending_for_teacher(db, current_user)


@router.post('/teacher/improvement/{submission_id}/override')
async def teacher_improvement_override(
    submission_id: str,
    request: ImprovementOverrideRequest,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await override_improvement(
        db,
        teacher=current_user,
        submission_id=submission_id,
        grade=request.grade,
        feedback=request.feedback,
    )


@router.get('/profiles/stream')
async def profile_stream() -> StreamingResponse:
    async def event_stream():
        demo_frames = [
            {'thought': '正在同步专业背景与前置知识，Mirror 置信度提升。'},
            {'thought': '检测到学习者偏好案例化解释，认知风格维度正在收敛。'},
            {'thought': '发现边界条件遗漏风险，易错倾向画像已更新。'},
        ]
        for frame in demo_frames:
            yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_stream(), media_type='text/event-stream')


# ----------------------------- 影子镜像推演（多智能体协同 · 时空扭曲沙盘） -----------------------------
_DIMENSIONS = [
    'major_background',
    'prior_knowledge',
    'cognitive_style',
    'mistake_tendency',
    'learning_goal',
    'time_flexibility',
    'modality_preference',
    'motivation_level',
]


def _safe_dim_score(raw: object) -> int:
    try:
        return max(0, min(100, int(round(float(raw)))))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _safe_dim_evidence(raw: object) -> list[str]:
    if isinstance(raw, str):
        return [raw] if raw.strip() else []
    if isinstance(raw, list):
        return [str(item) for item in raw if item is not None and str(item).strip()]
    return []


def _build_profile_extract(profile_model, overrides: dict[str, int] | None = None) -> StudentProfileExtract:
    """将 ORM 画像转为推演所需的 StudentProfileExtract，并应用维度分数覆盖（时空扭曲）。"""
    profile = StudentProfileExtract(student_name=getattr(profile_model, 'student_name', '星轨学习者') or '星轨学习者')
    overrides = overrides or {}
    for key in _DIMENSIONS:
        dim = getattr(profile_model, key, None)
        target = getattr(profile, key)
        if isinstance(dim, dict):
            target.value = str(dim.get('value') or '')
            score_raw = dim.get('score', 0)
            target.score = _safe_dim_score(0 if score_raw is None else score_raw)
            target.evidence = _safe_dim_evidence(dim.get('evidence'))
        else:
            target.value = ''
            target.score = 0
            target.evidence = []
        if key in overrides:
            try:
                target.score = max(0, min(100, int(overrides[key])))
            except (TypeError, ValueError):
                pass
    return profile


_DIM_VALUE_LABELS = {
    'major_background': '沙盘模拟专业背景',
    'prior_knowledge': '沙盘模拟前置知识',
    'cognitive_style': '沙盘模拟认知风格',
    'mistake_tendency': '沙盘模拟易错倾向',
    'learning_goal': '沙盘模拟学习目标',
    'time_flexibility': '沙盘模拟时间弹性',
    'modality_preference': '沙盘模拟资源模态偏好',
    'motivation_level': '沙盘模拟学习动机强度',
}


def _synthetic_profile_from_overrides(
    overrides: dict[str, int] | None = None,
    *,
    student_name: str = '沙盘模拟学生',
) -> StudentProfileExtract:
    """教师端时空扭曲沙盘：无真实画像时，仅用滑杆维度构造合成画像。"""
    profile = StudentProfileExtract(student_name=student_name or '沙盘模拟学生')
    overrides = overrides or {}
    for key in _DIMENSIONS:
        target = getattr(profile, key)
        target.value = _DIM_VALUE_LABELS.get(key, key)
        target.evidence = ['教师端时空扭曲沙盘合成画像']
        try:
            target.score = max(0, min(100, int(overrides.get(key, 50))))
        except (TypeError, ValueError):
            target.score = 50
    return profile


def _simulation_start_params(
    *,
    profile,
    subject_user_id: str,
    request: MirrorSimulationRequest,
    mode: str,
    synthetic_student_name: str = '',
) -> tuple[str, dict, bool]:
    """返回 (profile_id, register_params, synthetic)。无画像但有 overrides 时走合成推演。"""
    overrides = request.dimension_overrides or {}
    synthetic = profile is None
    if synthetic and not overrides:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='请先完成学生画像抽取')
    profile_id = '' if synthetic else profile.id
    params = {
        'profile_id': profile_id,
        'user_id': subject_user_id,
        'topic': request.topic,
        'planet_slug': (request.planet_slug or '').strip(),
        'target_dimension': request.target_dimension,
        'overrides': overrides,
        'mode': mode,
        'synthetic': synthetic,
        'synthetic_student_name': synthetic_student_name or '',
    }
    return profile_id, params, synthetic


async def _resolve_simulation_subject(
    db: AsyncSession,
    current_user,
    request: MirrorSimulationRequest,
):
    """解析推演主体画像：支持教师指定班级学生；返回 (profile, subject_user_id, synthetic_name)。"""
    from sqlalchemy import select

    from app.models.user import User

    target_user_id = (request.user_id or '').strip()
    profile_id = (request.student_profile_id or '').strip()

    # 学生自推演：忽略请求中的他人 user_id
    if current_user.role == 'student':
        profile = None
        if profile_id:
            profile = await get_profile_by_id(db, profile_id)
            if profile and profile.user_id and profile.user_id != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权使用该画像')
        if profile is None:
            profile = await get_latest_profile(db, user_id=current_user.id)
        return profile, current_user.id, current_user.display_name or ''

    # 教师 / 管理员：可指定班级学生
    if target_user_id and target_user_id != current_user.id:
        if current_user.role not in ('teacher', 'admin'):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='无权指定学生推演')
        student = (
            await db.execute(select(User).where(User.id == target_user_id, User.role == 'student'))
        ).scalar_one_or_none()
        if student is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='目标学生不存在')
        if current_user.role == 'teacher':
            allowed = await teacher_service._students(db, current_user, '')
            if student.id not in {s.id for s in allowed}:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='该学生不在您的班级中')
        profile = None
        if profile_id:
            profile = await get_profile_by_id(db, profile_id)
            if profile and profile.user_id and profile.user_id != student.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='画像与目标学生不匹配')
        if profile is None:
            profile = await get_latest_profile(db, user_id=student.id)
        return profile, student.id, student.display_name or student.username

    # 未指定学生：沿用当前用户自身画像（教师沙盘默认合成）
    profile = None
    if profile_id:
        profile = await get_profile_by_id(db, profile_id)
    if profile is None:
        profile = await get_latest_profile(db, user_id=current_user.id)
    return profile, current_user.id, current_user.display_name or ''


@router.post('/simulations/mirror', response_model=MirrorSimulationResponse)
async def mirror_simulation(
    request: MirrorSimulationRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> MirrorSimulationResponse:
    profile, subject_user_id, synthetic_name = await _resolve_simulation_subject(db, current_user, request)
    profile_id, run_params, _synthetic = _simulation_start_params(
        profile=profile,
        subject_user_id=subject_user_id,
        request=request,
        mode='mirror',
        synthetic_student_name=synthetic_name,
    )
    run_id = f'run-{uuid.uuid4().hex[:12]}'
    try:
        db.add(
            SimulationRun(
                id=run_id,
                user_id=current_user.id,
                profile_id=profile_id,
                topic=request.topic,
                mode='mirror',
                status='running',
            )
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception('mirror simulation start failed: %s', exc)
        detail = str(exc)
        exc_name = type(exc).__name__
        if 'Unknown column' in detail or 'OperationalError' in exc_name:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='推演落库失败：simulation_runs 表结构需迁移，请重启后端后再试。',
            ) from exc
        if 'DataError' in exc_name or 'Data too long' in detail:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='推演落库失败：run_id 超长或数据非法。',
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'推演启动失败：{exc_name}',
        ) from exc
    register_run(run_id, run_params)
    return MirrorSimulationResponse(run_id=run_id, status='running', topic=request.topic, mode='mirror')


@router.post('/simulations/multiverse', response_model=MirrorSimulationResponse)
async def multiverse_simulation(
    request: MirrorSimulationRequest,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> MirrorSimulationResponse:
    profile, subject_user_id, synthetic_name = await _resolve_simulation_subject(db, current_user, request)
    profile_id, run_params, _synthetic = _simulation_start_params(
        profile=profile,
        subject_user_id=subject_user_id,
        request=request,
        mode='multiverse',
        synthetic_student_name=synthetic_name,
    )
    run_id = f'mv-{uuid.uuid4().hex[:12]}'
    try:
        db.add(
            SimulationRun(
                id=run_id,
                user_id=current_user.id,
                profile_id=profile_id,
                topic=request.topic,
                mode='multiverse',
                status='running',
            )
        )
        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.exception('multiverse simulation start failed: %s', exc)
        detail = str(exc)
        exc_name = type(exc).__name__
        if 'Unknown column' in detail or 'OperationalError' in exc_name:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='推演落库失败：simulation_runs 表结构需迁移，请重启后端后再试。',
            ) from exc
        if 'DataError' in exc_name or 'Data too long' in detail:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail='推演落库失败：run_id 超长或数据非法。',
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f'推演启动失败：{exc_name}',
        ) from exc
    register_run(run_id, run_params)
    return MirrorSimulationResponse(run_id=run_id, status='running', topic=request.topic, mode='multiverse')


@router.get('/simulations/{run_id}/stream')
async def mirror_simulation_stream(
    run_id: str,
    current_user=Depends(require_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    params = get_run(run_id) or {}
    topic = params.get('topic') or '数据结构与算法基础'
    overrides = params.get('overrides') or {}
    mode = params.get('mode') or 'mirror'
    target_dimension = params.get('target_dimension')
    user_id = params.get('user_id') or current_user.id
    synthetic = bool(params.get('synthetic'))
    profile_id = params.get('profile_id') or ''
    synthetic_student_name = params.get('synthetic_student_name') or '沙盘模拟学生'

    async def event_stream():
        profile_model = None
        if not synthetic:
            if profile_id:
                profile_model = await get_profile_by_id(db, profile_id)
            if profile_model is None:
                profile_model = await get_latest_profile(db, user_id=user_id)
        if profile_model is None:
            if synthetic or overrides:
                profile = _synthetic_profile_from_overrides(
                    overrides,
                    student_name=synthetic_student_name,
                )
            else:
                yield format_sse({'role': 'System', 'type': 'evaluation', 'content': '尚未找到学生画像，无法启动推演。', 'payload': {}})
                return
        else:
            profile = _build_profile_extract(profile_model, overrides)
        runner = run_multiverse_simulation if mode == 'multiverse' else run_mirror_simulation
        root_cause = ''
        steps: list[str] = []
        plan_created = False
        skip_remediation = synthetic or profile_model is None
        async for event in runner(profile, topic, run_id=run_id, db=db):
            try:
                db.add(
                    SimulationEventRow(
                        id=str(uuid.uuid4()),
                        run_id=run_id,
                        role=str(event.get('role') or 'System'),
                        event_type=str(event.get('type') or 'info'),
                        content=str(event.get('content') or ''),
                        payload=event.get('payload') or {},
                    )
                )
                await db.commit()
            except Exception:
                await db.rollback()

            et = event.get('type')
            payload = event.get('payload') or {}
            if et == 'root_cause':
                root_cause = str(payload.get('root_cause') or event.get('content') or '')
            if et == 'learning_path':
                raw_steps = payload.get('steps') or []
                if isinstance(raw_steps, list):
                    steps = [str(s) for s in raw_steps]
                if steps and not plan_created and not skip_remediation:
                    try:
                        plan = await create_remediation_plan(
                            db,
                            user_id=user_id,
                            simulation_run_id=run_id,
                            topic=topic,
                            root_cause=root_cause,
                            steps=steps,
                            target_dimension=target_dimension,
                        )
                        plan_created = True
                        event = {
                            **event,
                            'payload': {
                                **payload,
                                'remediation_plan_id': plan.id,
                                'target_dimension': plan.target_dimension,
                            },
                        }
                    except Exception:
                        await db.rollback()
            if et == 'done':
                run_row = await db.get(SimulationRun, run_id)
                if run_row:
                    run_row.status = 'completed'
                    await db.commit()
                try:
                    from app.services.calibration import write_prediction

                    passed = bool(payload.get('passed'))
                    weak_steps = payload.get('steps') or steps
                    if not isinstance(weak_steps, list):
                        weak_steps = []
                    await write_prediction(
                        db,
                        user_id=str(user_id),
                        planet_slug=str(params.get('planet_slug') or ''),
                        sim_run_id=run_id,
                        predicted_fail=not passed,
                        weaknesses=[str(s) for s in weak_steps],
                        root_cause=root_cause,
                        topic=topic,
                    )
                except Exception:
                    await db.rollback()
            yield format_sse(event)

    return StreamingResponse(event_stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ---------------------------------------------------------------------------
# 教师端扩展套件（题库 / 成绩分析 / 待办 / 私信 / Agent 观测 / 资源审核 / 错题热点 / 日历 / 分组 / 激励 / 周报）
# ---------------------------------------------------------------------------


@router.get('/teacher/question-bank')
async def teacher_question_bank_list(
    galaxy_slug: str = '',
    difficulty: str = '',
    q: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await teacher_suite_service.list_questions(
        db, current_user, galaxy_slug=galaxy_slug, difficulty=difficulty, q=q
    )


@router.post('/teacher/question-bank')
async def teacher_question_bank_create(
    request: QuestionIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.create_question(db, current_user, request.model_dump())


@router.post('/teacher/question-bank/bulk')
async def teacher_question_bank_bulk(
    request: QuestionBulkIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.bulk_create_questions(
        db,
        current_user,
        questions=[q.model_dump() for q in request.questions],
        class_id=request.class_id,
        galaxy_slug=request.galaxy_slug,
        source=request.source,
    )


@router.post('/teacher/question-bank/ai-generate')
async def teacher_question_bank_ai_generate(
    request: QuestionAiGenerateIn,
    current_user=Depends(require_teacher),
) -> dict:
    return await teacher_suite_service.ai_generate_questions(
        current_user, topic=request.topic, count=request.count, difficulty=request.difficulty
    )


@router.post('/teacher/question-bank/import-from-assignment')
async def teacher_question_bank_import(
    request: QuestionImportAssignmentIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.import_questions_from_assignment(
            db, current_user, request.assignment_id, request.class_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put('/teacher/question-bank/{question_id}')
async def teacher_question_bank_update(
    question_id: str,
    request: QuestionUpdateIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.update_question(db, current_user, question_id, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete('/teacher/question-bank/{question_id}')
async def teacher_question_bank_delete(
    question_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.delete_question(db, current_user, question_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get('/teacher/assignments/{assignment_id}/analysis')
async def teacher_assignment_analysis(
    assignment_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.assignment_analysis(db, current_user, assignment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get('/teacher/gradebook/trends')
async def teacher_gradebook_trends(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.gradebook_trends(db, current_user, class_id)


@router.get('/teacher/todos')
async def teacher_todos(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.teacher_todos(db, current_user, class_id)


@router.get('/teacher/dm/conversations')
async def teacher_dm_conversations(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await teacher_suite_service.list_dm_conversations(db, current_user, class_id)


@router.get('/teacher/dm/{student_id}')
async def teacher_dm_messages(
    student_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await teacher_suite_service.list_direct_messages(db, current_user, student_id)


@router.post('/teacher/dm')
async def teacher_dm_send(
    request: DirectMessageSendIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.send_direct_message(db, current_user, request.student_id, request.body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/teacher/agent-runs')
async def teacher_agent_runs(
    class_id: str = '',
    limit: int = 80,
    scene: str = '',
    mode: str = '',
    status_filter: str = '',
    user_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await teacher_suite_service.teacher_agent_runs(
        db,
        current_user,
        class_id=class_id,
        limit=limit,
        scene=scene,
        mode=mode,
        status=status_filter,
        user_id=user_id,
    )


@router.get('/teacher/agent-runs/{run_id}')
async def teacher_agent_run_detail(
    run_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    detail = await teacher_suite_service.teacher_agent_run_detail(db, current_user, run_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Agent run 不存在或无权查看')
    return detail


@router.get('/teacher/generated-resources')
async def teacher_generated_resources(
    class_id: str = '',
    review_status: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await teacher_suite_service.list_student_generated_resources(
        db, current_user, class_id=class_id, status=review_status
    )


@router.post('/teacher/generated-resources/{resource_id}/review')
async def teacher_generated_resource_review(
    resource_id: str,
    request: ResourceReviewIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.review_generated_resource(
            db, current_user, resource_id, status=request.status, comment=request.comment
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post('/teacher/generated-resources/{resource_id}/recommend')
async def teacher_generated_resource_recommend(
    resource_id: str,
    request: ResourceRecommendIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.recommend_generated_resource(
            db, current_user, resource_id, class_id=request.class_id, galaxy_slug=request.galaxy_slug
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/teacher/insight/mistakes')
async def teacher_insight_mistakes(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.mistake_hotspots(db, current_user, class_id)


@router.post('/teacher/insight/mistakes/dispatch')
async def teacher_insight_mistakes_dispatch(
    request: MistakeDispatchIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.dispatch_hotspot_review(
            db, current_user, class_id=request.class_id, planet_slug=request.planet_slug, message=request.message
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/teacher/calendar')
async def teacher_calendar(
    class_id: str = '',
    month: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.calendar_month(db, current_user, class_id=class_id, month=month)


@router.post('/teacher/calendar')
async def teacher_calendar_create(
    request: CalendarEventIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.create_calendar_event(db, current_user, request.model_dump())


@router.delete('/teacher/calendar/{event_id}')
async def teacher_calendar_delete(
    event_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.delete_calendar_event(db, current_user, event_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get('/teacher/groups')
async def teacher_groups(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await teacher_suite_service.list_groups(db, current_user, class_id)


@router.post('/teacher/groups')
async def teacher_group_create(
    request: GroupIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.create_group(db, current_user, request.model_dump())


@router.put('/teacher/groups/{group_id}')
async def teacher_group_update(
    group_id: str,
    request: GroupUpdateIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.update_group(db, current_user, group_id, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.delete('/teacher/groups/{group_id}')
async def teacher_group_delete(
    group_id: str,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.delete_group(db, current_user, group_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post('/teacher/groups/{group_id}/dispatch')
async def teacher_group_dispatch(
    group_id: str,
    request: GroupDispatchIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.dispatch_to_group(
            db, current_user, group_id, message=request.message, planet_slug=request.planet_slug
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post('/teacher/praise')
async def teacher_praise_create(
    request: PraiseIn,
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        return await teacher_suite_service.create_praise(db, current_user, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get('/teacher/praise')
async def teacher_praise_overview(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.praise_overview(db, current_user, class_id)


@router.get('/teacher/weekly-report')
async def teacher_weekly_report(
    class_id: str = '',
    current_user=Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await teacher_suite_service.weekly_report(db, current_user, class_id)
