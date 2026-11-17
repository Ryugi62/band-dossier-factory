"""Account rules (§6): validation, scrypt password hashing, tokens."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets

from . import errors

_EMAIL = re.compile(r"[^@\s]+@[^@\s]+")
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
                             dklen=len(digest) // 2)
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got.hex(), digest)


def is_password_hash(stored) -> bool:
    if not isinstance(stored, str):
        return False
    parts = stored.split("$")
    return len(parts) == 6 and parts[0] == "scrypt" and all(parts[1:])


async def hash_password_async(password: str) -> str:
    return await asyncio.get_running_loop().run_in_executor(None, hash_password, password)


async def verify_password_async(password: str, stored: str) -> bool:
    return await asyncio.get_running_loop().run_in_executor(None, verify_password, password, stored)


def email_key(email: str) -> str:
    return email.lower()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def new_user_id() -> str:
    return "u_" + secrets.token_hex(8)


def require_strs(body: dict, *names: str) -> list[str]:
    """The named string fields: a present field of another JSON type is 400, a missing one 422."""
    for name in names:
        if body.get(name) is not None and not isinstance(body[name], str):
            raise errors.malformed(f"{name} must be a string")
    for name in names:
        if body.get(name) is None:
            raise errors.invalid(f"{name} is required")
    return [body[name] for name in names]


def validate_signup(body: dict) -> tuple[str, str, str]:
    email, password, display_name = require_strs(body, "email", "password", "display_name")
    validate_email(email)
    if len(password) < 8:
        raise errors.invalid("password must be at least 8 characters")
    if not display_name or len(display_name) > 100:
        raise errors.invalid("display_name must be 1 to 100 characters")
    return email, password, display_name


def validate_email(email: str) -> None:
    if not _EMAIL.fullmatch(email):
        raise errors.invalid("email must be of the form local@domain")


def validate_login(body: dict) -> tuple[str, str]:
    email, password = require_strs(body, "email", "password")
    return email, password
