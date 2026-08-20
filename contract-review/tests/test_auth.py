from contract_review.common.auth import (
    ROLE_ADMIN,
    SessionManager,
    UserInfo,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    stored = hash_password("s3cret-pass")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("s3cret-pass", stored) is True


def test_password_hash_rejects_wrong_password():
    stored = hash_password("correct-horse")
    assert verify_password("wrong-horse", stored) is False


def test_password_hash_is_salted():
    assert hash_password("same-password") != hash_password("same-password")


def test_password_hash_rejects_malformed():
    assert verify_password("anything", "not-a-valid-hash") is False
    assert verify_password("anything", "") is False


def _user() -> UserInfo:
    return UserInfo(id="11111111-1111-1111-1111-111111111111", username="alice", display_name="Alice", role=ROLE_ADMIN, is_active=True)


def test_session_roundtrip():
    manager = SessionManager("secret", 3600)
    token = manager.create(_user())
    payload = manager.read(token)
    assert payload is not None
    assert payload["username"] == "alice"
    assert payload["role"] == ROLE_ADMIN


def test_session_rejects_tampered_token():
    manager = SessionManager("secret", 3600)
    token = manager.create(_user())
    assert manager.read(token + "x") is None


def test_session_expires():
    manager = SessionManager("secret", -1)  # already expired
    token = manager.create(_user())
    assert manager.read(token) is None
