import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.core.config import get_settings

LEGACY_PREFIX = "sha256:"
SALTED_PREFIX = "pbkdf2:"
LEGACY_TOKEN_PREFIX = "token-"

logger = logging.getLogger(__name__)

try:
    import jwt
except ImportError:  # pragma: no cover
    jwt = None  # type: ignore


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()
    return f"{SALTED_PREFIX}{salt}${digest}"


def _legacy_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(plain_password: str, password_hash: str) -> bool:
    if password_hash.startswith(SALTED_PREFIX):
        payload = password_hash.removeprefix(SALTED_PREFIX)
        salt, expected = payload.split("$", 1)
        actual = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            120_000,
        ).hex()
        return hmac.compare_digest(actual, expected)
    if password_hash.startswith(LEGACY_PREFIX):
        return hmac.compare_digest(password_hash.removeprefix(LEGACY_PREFIX), _legacy_hash(plain_password))
    return hmac.compare_digest(password_hash, _legacy_hash(plain_password))


def create_access_token(*, user_id: str, role: str, expires_hours: Optional[int] = None) -> str:
    """签发 HS256 JWT；未安装 PyJWT 时回退为兼容旧格式 token-{id}。"""
    settings = get_settings()
    hours = expires_hours if expires_hours is not None else int(settings.jwt_expire_hours)
    if jwt is None:
        logger.warning("PyJWT 未安装，回退签发 legacy token-{id}")
        return f"{LEGACY_TOKEN_PREFIX}{user_id}"

    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=max(1, hours))).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """校验 JWT，成功返回 payload；失败返回 None。"""
    if not token or jwt is None:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        if not isinstance(payload, dict) or not payload.get("sub"):
            return None
        return payload
    except Exception:  # noqa: BLE001
        return None


def resolve_user_id_from_token(token: str) -> Optional[str]:
    """从 Bearer token 解析 user_id：优先 JWT，兼容 legacy token-{id}。"""
    raw = (token or "").strip()
    if not raw:
        return None
    payload = decode_access_token(raw)
    if payload and payload.get("sub"):
        return str(payload["sub"])
    if raw.startswith(LEGACY_TOKEN_PREFIX):
        uid = raw.removeprefix(LEGACY_TOKEN_PREFIX).strip()
        if uid:
            logger.debug("accepted legacy token- prefix for user_id=%s", uid[:8])
            return uid
    return None
