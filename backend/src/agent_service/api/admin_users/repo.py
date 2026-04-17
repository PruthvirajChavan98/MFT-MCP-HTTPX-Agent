"""Repository layer for the ``admin_users`` table.

Stateless — every method takes ``pool`` as the first parameter. Route
handlers orchestrate, this module owns SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class AdminUserRow:
    id: UUID
    email: str
    password_hash: str
    totp_secret_enc: str
    is_super_admin: bool
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None
    created_by_admin_id: UUID | None


@dataclass(frozen=True)
class AdminUserPublic:
    """Projection safe to return from list/get endpoints — never includes secrets."""

    id: UUID
    email: str
    is_super_admin: bool
    created_at: datetime
    revoked_at: datetime | None
    created_by_admin_id: UUID | None


def _row_to_admin(row: Any) -> AdminUserRow:
    return AdminUserRow(
        id=row["id"],
        email=row["email"],
        password_hash=row["password_hash"],
        totp_secret_enc=row["totp_secret_enc"],
        is_super_admin=row["is_super_admin"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        revoked_at=row["revoked_at"],
        created_by_admin_id=row["created_by_admin_id"],
    )


def _row_to_public(row: Any) -> AdminUserPublic:
    # Intentional subset of _row_to_admin — omits password_hash and
    # totp_secret_enc. When adding new fields to AdminUserRow, decide here
    # whether the public projection needs them (default: no).
    return AdminUserPublic(
        id=row["id"],
        email=row["email"],
        is_super_admin=row["is_super_admin"],
        created_at=row["created_at"],
        revoked_at=row["revoked_at"],
        created_by_admin_id=row["created_by_admin_id"],
    )


class AdminUsersRepo:
    """Data access for admin identities."""

    async def find_by_email_active(self, pool: Any, email: str) -> AdminUserRow | None:
        """Find an active (non-revoked) admin by email. Email is lowercased."""
        row = await pool.fetchrow(
            """
            SELECT id, email, password_hash, totp_secret_enc, is_super_admin,
                   created_at, updated_at, revoked_at, created_by_admin_id
            FROM admin_users
            WHERE email = $1 AND revoked_at IS NULL
            """,
            email.strip().lower(),
        )
        return _row_to_admin(row) if row else None

    async def find_by_id(self, pool: Any, user_id: UUID) -> AdminUserRow | None:
        """Find an admin by id regardless of revocation status."""
        row = await pool.fetchrow(
            """
            SELECT id, email, password_hash, totp_secret_enc, is_super_admin,
                   created_at, updated_at, revoked_at, created_by_admin_id
            FROM admin_users
            WHERE id = $1
            """,
            user_id,
        )
        return _row_to_admin(row) if row else None

    async def list_active(self, pool: Any) -> list[AdminUserPublic]:
        """Return all active admins ordered by created_at ascending."""
        rows = await pool.fetch(
            """
            SELECT id, email, is_super_admin, created_at, revoked_at, created_by_admin_id
            FROM admin_users
            WHERE revoked_at IS NULL
            ORDER BY created_at ASC
            """,
        )
        return [_row_to_public(r) for r in rows]

    async def count_active_super_admins(self, pool: Any) -> int:
        row = await pool.fetchrow(
            """
            SELECT COUNT(*)::int AS n
            FROM admin_users
            WHERE revoked_at IS NULL AND is_super_admin = TRUE
            """,
        )
        return int(row["n"]) if row else 0

    async def create(
        self,
        pool: Any,
        *,
        email: str,
        password_hash: str,
        totp_secret_enc: str,
        is_super_admin: bool = False,
        created_by_admin_id: UUID | None = None,
    ) -> AdminUserRow:
        """Insert a new admin. Caller must supply already-hashed password and
        already-Fernet-encrypted TOTP secret."""
        row = await pool.fetchrow(
            """
            INSERT INTO admin_users (
                email, password_hash, totp_secret_enc,
                is_super_admin, created_by_admin_id
            )
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, email, password_hash, totp_secret_enc, is_super_admin,
                      created_at, updated_at, revoked_at, created_by_admin_id
            """,
            email.strip().lower(),
            password_hash,
            totp_secret_enc,
            is_super_admin,
            created_by_admin_id,
        )
        return _row_to_admin(row)

    async def revoke(self, pool: Any, user_id: UUID) -> bool:
        """Soft-delete an admin. Returns True if a row was updated."""
        result = await pool.execute(
            """
            UPDATE admin_users
            SET revoked_at = now()
            WHERE id = $1 AND revoked_at IS NULL
            """,
            user_id,
        )
        # asyncpg execute returns "UPDATE N"
        try:
            _, count = result.split()
            return int(count) > 0
        except (ValueError, AttributeError):
            return False

    async def revoke_if_not_last_super(self, pool: Any, user_id: UUID) -> str:
        """Atomically revoke an admin, rejecting the revoke if it would
        leave zero active super-admins.

        Wraps the lookup + count + update in a single transaction with
        ``SELECT ... FOR UPDATE`` on the target row, closing the TOCTOU
        window that two concurrent revokes could otherwise exploit to
        zero out the super-admin set.

        Returns one of:
        - ``"ok"``         — row revoked
        - ``"not_found"``  — row missing or already revoked
        - ``"last_super"`` — target is super-admin and is the last active
                            one; no write performed
        """
        async with pool.acquire() as conn:
            async with conn.transaction():
                target_row = await conn.fetchrow(
                    """
                    SELECT is_super_admin
                    FROM admin_users
                    WHERE id = $1 AND revoked_at IS NULL
                    FOR UPDATE
                    """,
                    user_id,
                )
                if target_row is None:
                    return "not_found"

                if target_row["is_super_admin"]:
                    # Count all currently-active super-admins under the same
                    # transaction so the target row's state is part of the
                    # snapshot. Any concurrent revoke against another super
                    # blocks on its own FOR UPDATE lock, serializing the
                    # "last super" decision.
                    count_row = await conn.fetchrow(
                        """
                        SELECT COUNT(*)::int AS n
                        FROM admin_users
                        WHERE revoked_at IS NULL AND is_super_admin = TRUE
                        """,
                    )
                    active_supers = int(count_row["n"]) if count_row else 0
                    if active_supers <= 1:
                        return "last_super"

                await conn.execute(
                    """
                    UPDATE admin_users
                    SET revoked_at = now()
                    WHERE id = $1 AND revoked_at IS NULL
                    """,
                    user_id,
                )
                return "ok"

    async def seed_super_admin_if_absent(
        self,
        pool: Any,
        *,
        email: str,
        password_hash: str,
        totp_secret_enc: str,
    ) -> AdminUserRow | None:
        """Seed the env-backed super-admin into the table on first boot.

        Idempotent: if *any* active super-admin already exists, does nothing.
        We guard on "any active super-admin" (not on the specific email) so
        that after a password rotation the env vars don't silently re-insert
        a stale row alongside the real one.
        """
        existing = await self.count_active_super_admins(pool)
        if existing > 0:
            return None
        return await self.create(
            pool,
            email=email,
            password_hash=password_hash,
            totp_secret_enc=totp_secret_enc,
            is_super_admin=True,
            created_by_admin_id=None,
        )

    async def detect_super_admin_rotation_drift(
        self, pool: Any, *, env_email: str, env_password_hash: str
    ) -> bool:
        """Return True when the env-backed super-admin matches an existing
        active row by email but the stored password hash differs from the env.

        Indicates the operator rotated ``SUPER_ADMIN_PASSWORD_HASH`` in
        ``.env`` without updating the DB. The seed skips silently in that
        case (guarded on count > 0), so login would continue to use the
        *old* hash from the DB. Surfacing this as a startup warning keeps
        the footgun visible to operators.
        """
        row = await pool.fetchrow(
            """
            SELECT password_hash
            FROM admin_users
            WHERE email = $1 AND revoked_at IS NULL AND is_super_admin = TRUE
            LIMIT 1
            """,
            env_email.strip().lower(),
        )
        if row is None:
            return False
        return row["password_hash"] != env_password_hash


# Module-level singleton — same convention as AdminAnalyticsRepo callers.
admin_users_repo = AdminUsersRepo()
