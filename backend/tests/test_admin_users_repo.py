from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.agent_service.api.admin_users.repo import AdminUsersRepo


class FakePool:
    """Minimal asyncpg-pool stub that records calls and returns canned rows."""

    def __init__(self) -> None:
        self.fetchrow_queue: list[Any] = []
        self.fetch_queue: list[list[Any]] = []
        self.execute_queue: list[str] = []
        self.calls: list[tuple[str, str, tuple[Any, ...]]] = []

    async def fetchrow(self, query: str, *args: Any) -> Any:
        self.calls.append(("fetchrow", query, args))
        return self.fetchrow_queue.pop(0) if self.fetchrow_queue else None

    async def fetch(self, query: str, *args: Any) -> list[Any]:
        self.calls.append(("fetch", query, args))
        return self.fetch_queue.pop(0) if self.fetch_queue else []

    async def execute(self, query: str, *args: Any) -> str:
        self.calls.append(("execute", query, args))
        return self.execute_queue.pop(0) if self.execute_queue else "UPDATE 0"


def _row(
    *,
    email: str,
    is_super_admin: bool = False,
    revoked_at: datetime | None = None,
    created_by: UUID | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "id": uuid4(),
        "email": email,
        "password_hash": "$argon2id$...",
        "totp_secret_enc": "gAAAAA_fake",
        "is_super_admin": is_super_admin,
        "created_at": now,
        "updated_at": now,
        "revoked_at": revoked_at,
        "created_by_admin_id": created_by,
    }


@pytest.mark.asyncio
async def test_create_inserts_and_returns_row():
    repo = AdminUsersRepo()
    pool = FakePool()
    pool.fetchrow_queue.append(_row(email="new@example.com"))

    result = await repo.create(
        pool,
        email="NEW@Example.com",
        password_hash="$argon2id$hash",
        totp_secret_enc="enc_secret",
        is_super_admin=False,
        created_by_admin_id=uuid4(),
    )

    assert result.email == "new@example.com"
    assert not result.is_super_admin
    method, query, args = pool.calls[0]
    assert method == "fetchrow"
    assert "INSERT INTO admin_users" in query
    # email must be lowercased before hitting the DB
    assert args[0] == "new@example.com"


@pytest.mark.asyncio
async def test_find_by_email_active_lowercases_input_and_filters_revoked():
    repo = AdminUsersRepo()
    pool = FakePool()
    pool.fetchrow_queue.append(_row(email="pruthvi@example.com"))

    found = await repo.find_by_email_active(pool, "  PRUTHVI@example.com  ")

    assert found is not None
    assert found.email == "pruthvi@example.com"
    method, query, args = pool.calls[0]
    assert method == "fetchrow"
    assert "revoked_at IS NULL" in query
    assert args[0] == "pruthvi@example.com"


@pytest.mark.asyncio
async def test_find_by_email_active_returns_none_on_miss():
    repo = AdminUsersRepo()
    pool = FakePool()
    # fetchrow_queue empty → returns None
    result = await repo.find_by_email_active(pool, "missing@example.com")
    assert result is None


@pytest.mark.asyncio
async def test_list_active_returns_public_projection():
    repo = AdminUsersRepo()
    pool = FakePool()
    pool.fetch_queue.append(
        [
            _row(email="a@example.com", is_super_admin=True),
            _row(email="b@example.com"),
        ]
    )

    rows = await repo.list_active(pool)

    assert [r.email for r in rows] == ["a@example.com", "b@example.com"]
    # public projection must not expose secrets
    assert not hasattr(rows[0], "password_hash")
    assert not hasattr(rows[0], "totp_secret_enc")
    method, query, _ = pool.calls[0]
    assert method == "fetch"
    assert "revoked_at IS NULL" in query
    assert "ORDER BY created_at ASC" in query


@pytest.mark.asyncio
async def test_count_active_super_admins():
    repo = AdminUsersRepo()
    pool = FakePool()
    pool.fetchrow_queue.append({"n": 2})

    assert await repo.count_active_super_admins(pool) == 2


@pytest.mark.asyncio
async def test_revoke_parses_update_count():
    repo = AdminUsersRepo()
    pool = FakePool()
    pool.execute_queue.append("UPDATE 1")
    assert await repo.revoke(pool, uuid4()) is True

    pool.execute_queue.append("UPDATE 0")
    assert await repo.revoke(pool, uuid4()) is False


@pytest.mark.asyncio
async def test_seed_super_admin_is_idempotent_when_super_exists():
    repo = AdminUsersRepo()
    pool = FakePool()
    # First call is the count → returns 1 (super already exists)
    pool.fetchrow_queue.append({"n": 1})

    result = await repo.seed_super_admin_if_absent(
        pool,
        email="super@example.com",
        password_hash="$argon2id$x",
        totp_secret_enc="enc",
    )

    assert result is None
    # Only the COUNT query should have fired — no INSERT
    assert len(pool.calls) == 1
    assert "COUNT(*)" in pool.calls[0][1]


@pytest.mark.asyncio
async def test_detect_super_admin_rotation_drift_true_when_hash_differs():
    """S-M2: env password hash rotation without DB update is surfaced."""
    repo = AdminUsersRepo()
    pool = FakePool()
    pool.fetchrow_queue.append({"password_hash": "$argon2id$old-hash"})
    drifted = await repo.detect_super_admin_rotation_drift(
        pool, env_email="super@example.com", env_password_hash="$argon2id$new-hash"
    )
    assert drifted is True


@pytest.mark.asyncio
async def test_detect_super_admin_rotation_drift_false_when_hash_matches():
    repo = AdminUsersRepo()
    pool = FakePool()
    pool.fetchrow_queue.append({"password_hash": "$argon2id$same-hash"})
    drifted = await repo.detect_super_admin_rotation_drift(
        pool, env_email="super@example.com", env_password_hash="$argon2id$same-hash"
    )
    assert drifted is False


@pytest.mark.asyncio
async def test_detect_super_admin_rotation_drift_false_when_no_row():
    """No active super-admin row (e.g., fresh DB) → nothing to drift from."""
    repo = AdminUsersRepo()
    pool = FakePool()
    # fetchrow_queue empty → returns None
    drifted = await repo.detect_super_admin_rotation_drift(
        pool, env_email="super@example.com", env_password_hash="$argon2id$hash"
    )
    assert drifted is False


@pytest.mark.asyncio
async def test_seed_super_admin_creates_when_none_exist():
    repo = AdminUsersRepo()
    pool = FakePool()
    # Count returns 0 → insert should happen
    pool.fetchrow_queue.append({"n": 0})
    pool.fetchrow_queue.append(_row(email="super@example.com", is_super_admin=True))

    result = await repo.seed_super_admin_if_absent(
        pool,
        email="Super@Example.com",
        password_hash="$argon2id$x",
        totp_secret_enc="enc",
    )

    assert result is not None
    assert result.is_super_admin
    assert result.email == "super@example.com"
    # COUNT query, then INSERT
    assert len(pool.calls) == 2
    assert "INSERT INTO admin_users" in pool.calls[1][1]
