"""JWT 签发与鉴权解析冒烟。"""

from app.core.security import (
    create_access_token,
    decode_access_token,
    resolve_user_id_from_token,
)


def test_jwt_roundtrip():
    token = create_access_token(user_id="user-abc", role="student")
    assert not token.startswith("token-"), "应签发 JWT 而非 legacy"
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-abc"
    assert payload["role"] == "student"
    assert resolve_user_id_from_token(token) == "user-abc"


def test_legacy_token_still_accepted():
    assert resolve_user_id_from_token("token-legacy-user-1") == "legacy-user-1"


def test_expired_jwt_rejected():
    import jwt
    from app.core.config import get_settings

    token = create_access_token(user_id="u1", role="admin", expires_hours=1)
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"verify_exp": False},
    )
    payload["exp"] = 1
    bad = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert decode_access_token(bad) is None
    assert resolve_user_id_from_token(bad) is None
