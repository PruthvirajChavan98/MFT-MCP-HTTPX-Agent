"""Repository layer for admin_enrollment_tokens.

Stateless — every method takes ``pool`` as the first parameter. Route handlers
orchestrate, this module owns the SQL and the atomic-redeem transaction.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID


@dataclass(frozen=True)
class EnrollmentTokenRow:
    """Internal representation — never serialized outside the repo."""

    token_hash: str
    email: str
    role: str
    created_by: UUID
    created_at: datetime
    expires_at: datetime
    consumed_at: datetime | None
    consumed_ip: str | None


@dataclass(frozen=True)
class IssuedToken:
    """Returned once by ``create_token`` — plaintext is never retrievable again."""

    plaintext: str
    token_hash: str
    email: str
    role: str
    expires_at: datetime


def _hash_token(plaintext: str) -> str:
    """SHA-256 hex digest. Deterministic so GET/redeem can look up without the plaintext."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _row_to_token(row: Any) -> EnrollmentTokenRow:
    return EnrollmentTokenRow(
        token_hash=row["token_hash"],
        email=row["email"],
        role=row["role"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        consumed_at=row["consumed_at"],
        consumed_ip=row["consumed_ip"],
    )


# Outcomes of an atomic redeem. Kept as a Literal so callers can exhaustively match.
RedeemOutcome = Literal["ok", "not_found", "expired", "consumed"]


class AdminEnrollmentRepo:
    """Data access + atomic redeem for enrollment tokens."""

    async def create_token(
        self,
        pool: Any,
        *,
        email: str,
        role: str,
        created_by: UUID,
        ttl_hours: int,
    ) -> IssuedToken:
        """Generate a fresh token, store its hash, return the plaintext ONCE.

        ``ttl_hours`` is clamped at the route layer; this method trusts the caller.
        """
        plaintext = secrets.token_urlsafe(32)  # 43 URL-safe chars
        token_hash = _hash_token(plaintext)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
        normalized_email = email.strip().lower()

        await pool.execute(
            """
            INSERT INTO admin_enrollment_tokens
                (token_hash, email, role, created_by, expires_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            token_hash,
            normalized_email,
            role,
            created_by,
            expires_at,
        )
        return IssuedToken(
            plaintext=plaintext,
            token_hash=token_hash,
            email=normalized_email,
            role=role,
            expires_at=expires_at,
        )

    async def find_by_plaintext(self, pool: Any, plaintext: str) -> EnrollmentTokenRow | None:
        """Look up a token by its plaintext (via SHA-256). Returns None on miss."""
        token_hash = _hash_token(plaintext)
        row = await pool.fetchrow(
            """
            SELECT token_hash, email, role, created_by,
                   created_at, expires_at, consumed_at, consumed_ip
            FROM admin_enrollment_tokens
            WHERE token_hash = $1
            """,
            token_hash,
        )
        return _row_to_token(row) if row else None

    async def consume_token_atomic(
        self,
        pool: Any,
        *,
        plaintext: str,
        password_hash: str,
        totp_secret_enc: str,
        consumed_ip: str | None,
    ) -> tuple[RedeemOutcome, UUID | None]:
        """Atomically validate + consume a token and create the admin_users row.

        Single transaction with ``SELECT ... FOR UPDATE`` on the token row so
        concurrent redeems of the same plaintext serialize and exactly one
        wins. Mirrors the pattern in
        ``admin_users/repo.py::revoke_if_not_last_super``.

        Returns:
            ("ok", admin_user_id) — admin row created, token marked consumed
            ("not_found", None)   — no token matches the plaintext
            ("expired", None)     — token exists but has passed expires_at
            ("consumed", None)    — token was already redeemed
        """
        token_hash = _hash_token(plaintext)

        async with pool.acquire() as conn:
            async with conn.transaction():
                token_row = await conn.fetchrow(
                    """
                    SELECT email, role, consumed_at, expires_at
                    FROM admin_enrollment_tokens
                    WHERE token_hash = $1
                    FOR UPDATE
                    """,
                    token_hash,
                )
                if token_row is None:
                    return ("not_found", None)

                if token_row["consumed_at"] is not None:
                    return ("consumed", None)

                now = datetime.now(timezone.utc)
                if token_row["expires_at"] <= now:
                    return ("expired", None)

                # Reject if an active admin with the bound email already exists —
                # prevents a token created before a prior direct-create flow from
                # later short-circuiting the uniqueness guard.
                existing = await conn.fetchrow(
                    """
                    SELECT 1
                    FROM admin_users
                    WHERE email = $1 AND revoked_at IS NULL
                    """,
                    token_row["email"],
                )
                if existing is not None:
                    # Treat as "consumed" for the caller — the enrollment
                    # opportunity is gone either way.
                    return ("consumed", None)

                new_admin_row = await conn.fetchrow(
                    """
                    INSERT INTO admin_users (
                        email, password_hash, totp_secret_enc,
                        is_super_admin, created_by_admin_id
                    )
                    VALUES ($1, $2, $3, $4, $5)
                    RETURNING id
                    """,
                    token_row["email"],
                    password_hash,
                    totp_secret_enc,
                    token_row["role"] == "super_admin",
                    None,
                )

                await conn.execute(
                    """
                    UPDATE admin_enrollment_tokens
                    SET consumed_at = now(), consumed_ip = $2
                    WHERE token_hash = $1
                    """,
                    token_hash,
                    consumed_ip,
                )

                return ("ok", new_admin_row["id"])


# Module-level singleton — matches the admin_users_repo convention.
admin_enrollment_repo = AdminEnrollmentRepo()
