from app.models.user import User
from app.schemas.auth import UserInfo
from app.services.pet_service import resolve_pet_slug


def user_to_info(user: User) -> UserInfo:
    return UserInfo(
        id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
        avatar=user.avatar,
        avatar_cartoon_url=user.avatar_cartoon_url,
        class_id=user.class_id,
        teacher_id=user.teacher_id,
        pet_slug=resolve_pet_slug(user.pet_slug),
        pet_affinity=int(user.pet_affinity or 0),
        equipped_title=user.equipped_title or "",
        study_theme=user.study_theme or "",
    )
