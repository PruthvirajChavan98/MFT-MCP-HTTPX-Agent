#!/usr/bin/env python3
"""Interactive enrollment script for the single super-admin account.

Generates all five environment variables needed to run the admin auth system
with ``ADMIN_AUTH_ENABLED=true``. Runs fully standalone — does not import the
project's ``config`` or ``admin_crypto`` modules to avoid the config-validator
dependency loop. Each generated value is self-verified via inline round-trip
before being printed.

Usage (from repo root):

    uv run python backend/scripts/enroll_super_admin.py

Or from any working directory:

    uv run --project backend python backend/scripts/enroll_super_admin.py

The script NEVER writes to a file. It prints the env var block to stdout so
you can paste it into your ``backend/.env`` (or ``.env.local`` / ``.env.uat``
/ ``.env.prod`` depending on which environment you are enrolling against).

All dependencies are already installed by ``uv sync`` in the backend project:
- ``pyotp``       (TOTP secret generation + URI)
- ``argon2-cffi`` (argon2id password hashing)
- ``cryptography`` (Fernet symmetric encryption for TOTP secret at rest)
- ``secrets``     (stdlib; urlsafe random for JWT signing key)
"""

from __future__ import annotations

import getpass
import re
import secrets as stdsecrets
import sys
from typing import NoReturn

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

_MIN_PASSWORD_LENGTH = 12
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ISSUER_NAME = "mft-agent-admin"


def _die(msg: str, code: int = 1) -> NoReturn:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _prompt_email() -> str:
    while True:
        try:
            email = input("Super-admin email: ").strip().lower()
        except EOFError:
            _die("enrollment aborted (EOF on email prompt)")
        if not email:
            print("  email must be non-empty")
            continue
        if not _EMAIL_RE.match(email):
            print(f"  {email!r} does not look like an email address")
            continue
        return email


def _prompt_password() -> str:
    while True:
        try:
            password = getpass.getpass("Super-admin password: ")
            confirm = getpass.getpass("Confirm password:     ")
        except EOFError:
            _die("enrollment aborted (EOF on password prompt)")
        if password != confirm:
            print("  passwords do not match, try again")
            continue
        if len(password) < _MIN_PASSWORD_LENGTH:
            print(f"  password must be at least {_MIN_PASSWORD_LENGTH} characters")
            continue
        return password


def _generate_jwt_secret() -> str:
    """32-byte url-safe random string — satisfies PyJWT 2.12.x HS256 length check."""
    # secrets.token_urlsafe(n) returns ~1.33n characters of url-safe base64.
    # Passing 32 yields a 43-char string whose UTF-8 byte length is 43 >= 32.
    return stdsecrets.token_urlsafe(32)


def _generate_fernet_key() -> str:
    """URL-safe base64 of 32 random bytes, as required by cryptography.fernet.Fernet."""
    return Fernet.generate_key().decode("utf-8")


def _hash_password_argon2id(plaintext: str) -> str:
    """Argon2id hash with the library's RFC 9106 low-memory profile defaults."""
    hasher = PasswordHasher()
    return hasher.hash(plaintext)


def _encrypt_totp_secret(plaintext_base32: str, fernet_key: str) -> str:
    """Fernet-encrypt the TOTP secret with the newly generated master key."""
    fernet = Fernet(fernet_key.encode("utf-8"))
    return fernet.encrypt(plaintext_base32.encode("utf-8")).decode("utf-8")


def _self_verify(
    *,
    jwt_secret: str,
    fernet_key: str,
    password: str,
    password_hash: str,
    totp_secret: str,
    encrypted_totp: str,
) -> None:
    """Round-trip every generated value before emitting the env block."""
    # 1. JWT secret length (RFC 7518 §3.2)
    if len(jwt_secret.encode("utf-8")) < 32:
        _die("generated JWT_SECRET is shorter than 32 bytes — retry enrollment")

    # 2. Fernet key validity + round-trip
    try:
        f = Fernet(fernet_key.encode("utf-8"))
    except ValueError as e:
        _die(f"generated FERNET_MASTER_KEY is malformed: {e}")
    probe = b"self-test-probe"
    if f.decrypt(f.encrypt(probe)) != probe:
        _die("Fernet round-trip failed — generated key is corrupt")

    # 3. Password hash round-trip via a fresh hasher instance
    hasher = PasswordHasher()
    try:
        if hasher.verify(password_hash, password) is not True:
            _die("argon2 verify returned non-True — password hash is corrupt")
    except VerifyMismatchError:
        _die("argon2 verify rejected the just-hashed password — impossible state")

    # 4. TOTP encrypted secret decrypts back to the plaintext
    try:
        decrypted = f.decrypt(encrypted_totp.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        _die("Fernet decrypt rejected the just-encrypted TOTP secret — corrupt state")
    if decrypted != totp_secret:
        _die("decrypted TOTP secret does not match the original — corrupt state")

    # 5. TOTP code generation + verification
    totp = pyotp.TOTP(totp_secret)
    code = totp.now()
    if not totp.verify(code, valid_window=1):
        _die("pyotp self-verification failed — TOTP secret is corrupt")


def _print_env_block(
    *,
    email: str,
    jwt_secret: str,
    fernet_key: str,
    password_hash: str,
    encrypted_totp: str,
    totp_secret: str,
) -> None:
    provisioning_uri = pyotp.TOTP(totp_secret).provisioning_uri(
        name=email, issuer_name=_ISSUER_NAME
    )

    print("\n" + "=" * 72)
    print("  ENROLLMENT COMPLETE — self-verification passed on all 5 values")
    print("=" * 72)

    print("\nStep 1 — register the TOTP secret with your authenticator app.")
    print("Either scan the URI below as a QR code, or manually enter the raw")
    print("base32 secret in 'add account' → 'enter key manually'.\n")
    print(f"  Provisioning URI: {provisioning_uri}")
    print(f"  Raw base32 secret: {totp_secret}")
    print(f"  Issuer:            {_ISSUER_NAME}")
    print(f"  Account:           {email}")

    print("\nStep 2 — paste the following block into backend/.env (or whichever")
    print("environment file you are enrolling against). Phase 6h will retire")
    print("the ADMIN_AUTH_ENABLED flag; until then it is the runtime kill switch.\n")
    print("-" * 72)
    print("ADMIN_AUTH_ENABLED=true")
    print(f"JWT_SECRET={jwt_secret}")
    print(f"FERNET_MASTER_KEY={fernet_key}")
    print(f"SUPER_ADMIN_EMAIL={email}")
    print(f"SUPER_ADMIN_PASSWORD_HASH={password_hash}")
    print(f"SUPER_ADMIN_TOTP_SECRET_ENC={encrypted_totp}")
    print("-" * 72)

    print("\nStep 3 — restart the backend so config.py picks up the new values.")
    print("Step 4 — open /admin/login in a browser, sign in, verify the dashboard loads.")
    print(
        "Step 5 — delete this terminal scrollback or clear your shell history;"
        " the JWT secret and hash above are sensitive.\n"
    )


def main() -> None:
    print("Super-admin enrollment — mft-mcp-httpx-agent")
    print("This session generates secrets locally and prints them to stdout.\n")

    email = _prompt_email()
    password = _prompt_password()

    jwt_secret = _generate_jwt_secret()
    fernet_key = _generate_fernet_key()
    password_hash = _hash_password_argon2id(password)
    totp_secret = pyotp.random_base32()
    encrypted_totp = _encrypt_totp_secret(totp_secret, fernet_key)

    _self_verify(
        jwt_secret=jwt_secret,
        fernet_key=fernet_key,
        password=password,
        password_hash=password_hash,
        totp_secret=totp_secret,
        encrypted_totp=encrypted_totp,
    )

    _print_env_block(
        email=email,
        jwt_secret=jwt_secret,
        fernet_key=fernet_key,
        password_hash=password_hash,
        encrypted_totp=encrypted_totp,
        totp_secret=totp_secret,
    )


if __name__ == "__main__":
    main()
