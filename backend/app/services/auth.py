from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User

DEMO_USERS = [
    {"username": "student001", "password": "123456", "role": "student", "display_name": "张三"},
    {"username": "teacher001", "password": "123456", "role": "teacher", "display_name": "李老师"},
    {"username": "admin001", "password": "123456", "role": "admin", "display_name": "系统管理员"},
]

ROLE_LABELS = {"student": "学生", "teacher": "教师", "admin": "管理员"}
VALID_ROLES = frozenset(ROLE_LABELS)


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    return (
        await session.execute(select(User).where(User.username == username.strip()))
    ).scalar_one_or_none()


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User | None:
    user = await get_user_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def role_mismatch_message(selected_role: str, actual_role: str) -> str:
    selected = ROLE_LABELS.get(selected_role, selected_role)
    actual = ROLE_LABELS.get(actual_role, actual_role)
    return f"账号角色为「{actual}」，与所选「{selected}」不一致"


async def preflight_username_role(session: AsyncSession, username: str, role: str) -> tuple[bool, str]:
    """校验用户名存在且角色与所选一致。返回 (ok, message)。"""
    role = (role or "").strip()
    if role not in VALID_ROLES:
        return False, "请选择有效角色"
    name = (username or "").strip()
    if not name:
        return False, "请输入用户名"
    user = await get_user_by_username(session, name)
    if user is None:
        return False, "用户名不存在"
    if user.role != role:
        return False, role_mismatch_message(role, user.role)
    return True, ""


async def check_username_available(session: AsyncSession, username: str) -> tuple[bool, str]:
    """注册前校验用户名是否可用。返回 (available, message)。"""
    name = (username or "").strip()
    if not name:
        return False, "请输入用户名"
    if len(name) < 3:
        return False, "用户名至少 3 个字符"
    user = await get_user_by_username(session, name)
    if user is not None:
        return False, "用户名已存在"
    return True, ""


async def seed_demo_users(session: AsyncSession) -> None:
    for item in DEMO_USERS:
        exists = (
            await session.execute(select(User).where(User.username == item["username"]))
        ).scalar_one_or_none()
        if exists is not None:
            continue
        session.add(
            User(
                username=item["username"],
                password_hash=hash_password(item["password"]),
                role=item["role"],
                display_name=item["display_name"],
            )
        )
    await session.commit()
