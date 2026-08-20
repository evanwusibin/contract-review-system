"""Database-backed authentication, HttpOnly session, and RBAC (Phase 3).

Design decisions:
- Passwords are hashed with stdlib PBKDF2-HMAC-SHA256 (600k iterations, OWASP 2023
  recommendation). No native dependency (bcrypt/argon2) is required, which keeps the
  container build hermetic; swap to argon2id later if a KDF policy demands it.
- Sessions use `itsdangerous` URLSafeTimedSerializer with SESSION_SECRET — the same
  signed-cookie approach the demo already depends on, now with an expiry (TTL).
- Users live in the PostgreSQL `users` table (Phase 1 baseline). The auth path is only
  active when AUTH_ENABLED=true (production gate), which also implies DATABASE_URL is
  set — so the sync session factory is safe to use here.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator
from uuid import UUID

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select

from contract_review.db import User as UserORM
from contract_review.database import get_sync_session_factory

PBKDF2_ALGO = "sha256"
PBKDF2_ITERATIONS = 600_000
PBKDF2_SALT_BYTES = 16

SESSION_COOKIE = "cr_session"

# Canonical role names (must stay in sync with users.role and review required_roles).
ROLE_ADMIN = "admin"
ROLE_BUSINESS = "business_reviewer"
ROLE_LEGAL = "legal_reviewer"
ROLE_WARRANTY = "warranty_reviewer"
ROLES = (ROLE_ADMIN, ROLE_BUSINESS, ROLE_LEGAL, ROLE_WARRANTY)


def hash_password(password: str) -> str:
    salt = os.urandom(PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "$".join(
        (
            "pbkdf2_sha256",
            str(PBKDF2_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_b64, hash_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        digest = hashlib.pbkdf2_hmac(PBKDF2_ALGO, password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class UserInfo:
    id: str
    username: str
    display_name: str | None
    role: str
    is_active: bool


class SessionManager:
    def __init__(self, secret: str, max_age: int) -> None:
        self._serializer = URLSafeTimedSerializer(secret, salt="contract-review-session")
        self.max_age = max_age

    def create(self, user: UserInfo) -> str:
        return self._serializer.dumps({"uid": user.id, "username": user.username, "role": user.role})

    def read(self, token: str) -> dict | None:
        try:
            return self._serializer.loads(token, max_age=self.max_age)
        except (BadSignature, SignatureExpired):
            return None


class UserRepository:
    """Sync access to the users table (matches the PostgresReviewStore pattern)."""

    def __init__(self) -> None:
        self._factory = get_sync_session_factory()

    @contextmanager
    def _session(self) -> Iterator:
        session = self._factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _to_info(row: UserORM) -> UserInfo:
        return UserInfo(
            id=str(row.id),
            username=row.username,
            display_name=row.display_name,
            role=row.role,
            is_active=row.is_active,
        )

    def get_by_username(self, username: str) -> UserInfo | None:
        with self._session() as s:
            row = s.execute(select(UserORM).where(UserORM.username == username)).scalar_one_or_none()
            return self._to_info(row) if row else None

    def get_by_id(self, user_id: str) -> UserInfo | None:
        with self._session() as s:
            row = s.get(UserORM, user_id)
            return self._to_info(row) if row else None

    def verify_credentials(self, username: str, password: str) -> UserInfo | None:
        with self._session() as s:
            row = s.execute(select(UserORM).where(UserORM.username == username)).scalar_one_or_none()
            if row is None or not row.is_active or not verify_password(password, row.password_hash):
                return None
            return self._to_info(row)

    def create_user(
        self, username: str, password: str, role: str, display_name: str | None = None
    ) -> UserInfo:
        if role not in ROLES:
            raise ValueError(f"unknown role: {role}")
        with self._session() as s:
            row = UserORM(
                username=username,
                password_hash=hash_password(password),
                display_name=display_name,
                role=role,
                is_active=True,
            )
            s.add(row)
            s.flush()
            return self._to_info(row)

    def count_users(self) -> int:
        with self._session() as s:
            return s.query(UserORM).count()

    def ensure_seed_users(self) -> None:
        """Idempotent bootstrap: create an admin + the three reviewer accounts.

        Credentials are read from the environment (with demo-safe defaults) so the
        production operator can override them. Only runs when the table is empty.
        """
        if self.count_users() > 0:
            return
        admin_pwd = os.getenv("ADMIN_PASSWORD", "admin123")
        self.create_user("admin", admin_pwd, ROLE_ADMIN, "系统管理员")
        for username, role, label in (
            ("business", ROLE_BUSINESS, "业务评审员"),
            ("legal", ROLE_LEGAL, "法务评审员"),
            ("warranty", ROLE_WARRANTY, "质保评审员"),
        ):
            self.create_user(username, os.getenv(f"{username.upper()}_PASSWORD", f"{username}123"), role, label)
