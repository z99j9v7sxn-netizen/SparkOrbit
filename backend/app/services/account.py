import logging
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.paths import AVATARS_DIR
from app.core.security import hash_password
from app.models.school_class import SchoolClass
from app.models.user import User
from app.services.avatar_service import generate_avatar
from app.services.chat_service import ensure_class_room_for_student

logger = logging.getLogger(__name__)

DEMO_CLASSES = [
    {"name": "计算机网络 2024-1 班", "invite_code": "NET2024A"},
    {"name": "操作系统 2024-1 班", "invite_code": "OS2024A"},
]


async def seed_classes(session: AsyncSession) -> None:
    teachers = (
        await session.execute(select(User).where(User.role == "teacher"))
    ).scalars().all()
    if not teachers:
        return

    existing = (await session.execute(select(SchoolClass))).scalars().first()
    if existing is not None:
        return

    teacher = teachers[0]
    for item in DEMO_CLASSES:
        session.add(
            SchoolClass(
                name=item["name"],
                teacher_id=teacher.id,
                invite_code=item["invite_code"],
            )
        )
    await session.commit()


async def list_teachers(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.role == "teacher"))
    return list(result.scalars().all())


async def list_classes(session: AsyncSession) -> list[tuple[SchoolClass, User | None]]:
    classes = (await session.execute(select(SchoolClass).order_by(SchoolClass.name))).scalars().all()
    out: list[tuple[SchoolClass, User | None]] = []
    for cls in classes:
        teacher = None
        if cls.teacher_id:
            teacher = (
                await session.execute(select(User).where(User.id == cls.teacher_id))
            ).scalar_one_or_none()
        out.append((cls, teacher))
    return out


async def _save_avatar_file(user_id: str, image_bytes: bytes, content_type: str) -> str:
    ext = ".jpg"
    if "png" in (content_type or ""):
        ext = ".png"
    elif "webp" in (content_type or ""):
        ext = ".webp"
    filename = f"{user_id}{ext}"
    path = AVATARS_DIR / filename
    path.write_bytes(image_bytes)
    return f"/static/uploads/avatars/{filename}"


async def register_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    display_name: str,
    role: str,
    teacher_id: str = "",
    class_id: str = "",
    description: str = "",
    photo: UploadFile | None = None,
) -> User:
    username = username.strip()
    if not username:
        raise ValueError("用户名不能为空")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")
    if role not in {"student", "teacher"}:
        raise ValueError("注册角色仅支持 student 或 teacher")

    exists = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if exists is not None:
        raise ValueError("用户名已存在")

    if teacher_id:
        teacher = (
            await session.execute(select(User).where(User.id == teacher_id, User.role == "teacher"))
        ).scalar_one_or_none()
        if teacher is None:
            raise ValueError("负责老师不存在")

    if class_id:
        cls = (await session.execute(select(SchoolClass).where(SchoolClass.id == class_id))).scalar_one_or_none()
        if cls is None:
            raise ValueError("班级不存在")
        if not teacher_id:
            teacher_id = cls.teacher_id

    user = User(
        id=str(uuid4()),
        username=username,
        password_hash=hash_password(password),
        role=role,
        display_name=display_name.strip() or username,
        teacher_id=teacher_id or "",
        class_id=class_id or "",
    )
    session.add(user)
    await session.flush()

    if photo is not None:
        image_bytes = await photo.read()
        if image_bytes:
            local_url = await _save_avatar_file(user.id, image_bytes, photo.content_type or "image/jpeg")
            user.avatar = local_url
            try:
                result = await generate_avatar(
                    image_bytes,
                    content_type=photo.content_type or "image/jpeg",
                    description=description,
                )
                user.avatar_cartoon_url = result["cartoon_url"]
            except Exception as exc:
                logger.warning("注册时卡通头像生成失败，使用本地原图: %s", exc)
                user.avatar_cartoon_url = local_url

    await session.commit()
    await session.refresh(user)

    if user.role == "student" and user.class_id:
        await ensure_class_room_for_student(session, user)

    return user


async def link_demo_student(session: AsyncSession) -> None:
    from app.models.school_class import SchoolClass

    student = (
        await session.execute(select(User).where(User.username == "student001"))
    ).scalar_one_or_none()
    teacher = (
        await session.execute(select(User).where(User.username == "teacher001"))
    ).scalar_one_or_none()
    cls = (await session.execute(select(SchoolClass).order_by(SchoolClass.name))).scalars().first()
    if student is None or teacher is None or cls is None:
        return
    changed = False
    if not student.class_id:
        student.class_id = cls.id
        changed = True
    if not student.teacher_id:
        student.teacher_id = teacher.id
        changed = True
    if changed:
        await session.commit()
        await ensure_class_room_for_student(session, student)


async def update_user_profile(
    session: AsyncSession,
    user: User,
    *,
    display_name: str | None = None,
    equipped_title: str | None = None,
    study_theme: str | None = None,
) -> User:
    if display_name is not None:
        name = display_name.strip()
        if not name:
            raise ValueError('昵称不能为空')
        user.display_name = name
    if equipped_title is not None:
        user.equipped_title = equipped_title.strip()
    if study_theme is not None:
        user.study_theme = study_theme.strip()
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
