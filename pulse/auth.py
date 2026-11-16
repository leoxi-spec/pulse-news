"""Email accounts and sessions, stored in the same SQLite file as the archive.

This is a self-hosted, single-file backend: `users`, `sessions` and `profiles`
live in pulse.sqlite3. There is no mail server, so email addresses are recorded
but not verified; the admin view can export every account to CSV.
"""
from __future__ import annotations

import csv
import hashlib
import hmac
import io
import re
import secrets
import time
from datetime import timedelta

from . import profiles
from .db import db
from .timeutil import iso, now, parse_iso

SESSION_COOKIE = "pulse_session"
SESSION_DAYS = 30
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_ATTEMPTS: dict[str, list[float]] = {}


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _hash(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 260_000)
    return digest.hex(), salt


def _verify(password: str, stored: str, salt: str) -> bool:
    digest, _ = _hash(password, salt)
    return hmac.compare_digest(digest, stored)


def _rate(key: str) -> None:
    now_ts = time.time()
    bucket = [stamp for stamp in _ATTEMPTS.get(key, []) if now_ts - stamp < 600]
    if len(bucket) >= 10:
        raise AuthError(429, "Too many attempts. Try again in a few minutes.")
    bucket.append(now_ts)
    _ATTEMPTS[key] = bucket


def _rate_ok(key: str) -> None:
    _ATTEMPTS.pop(key, None)


def public(user: dict | None) -> dict | None:
    if not user:
        return None
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user.get("name") or "",
        "is_admin": bool(user.get("is_admin")),
        "profile_id": user.get("profile_id"),
        "created_at": user.get("created_at"),
        "last_login_at": user.get("last_login_at"),
    }


def _by_email(email: str) -> dict | None:
    row = db.query_one("SELECT * FROM users WHERE email=?", (email,))
    return dict(row) if row else None


def _by_token(token: str) -> dict | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    row = db.query_one(
        """SELECT u.*, s.expires_at, s.last_seen_at FROM sessions s
           JOIN users u ON u.id = s.user_id WHERE s.token_hash=?""",
        (token_hash,),
    )
    if not row:
        return None
    if parse_iso(row["expires_at"]) < now():
        db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))
        return None
    seen = parse_iso(row["last_seen_at"]) if row["last_seen_at"] else None
    if not seen or (now() - seen) > timedelta(hours=1):
        db.execute("UPDATE sessions SET last_seen_at=? WHERE token_hash=?", (iso(), token_hash))
    return dict(row)


def _create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = iso(now() + timedelta(days=SESSION_DAYS))
    db.execute(
        "INSERT INTO sessions(token_hash, user_id, created_at, expires_at, last_seen_at) VALUES(?,?,?,?,?)",
        (token_hash, user_id, iso(), expiry, iso()),
    )
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (iso(),))
    return token


def session_user(request) -> dict | None:
    raw = request.headers.get("cookie") or ""
    token = None
    for part in raw.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key.strip() == SESSION_COOKIE:
                token = value.strip()
                break
    return _by_token(token) if token else None


def session_token(request) -> str | None:
    raw = request.headers.get("cookie") or ""
    for part in raw.split(";"):
        if "=" in part:
            key, value = part.split("=", 1)
            if key.strip() == SESSION_COOKIE:
                return value.strip()
    return None


def cookie(token: str, *, secure: bool = False) -> str:
    parts = [f"{SESSION_COOKIE}={token}", "Path=/", f"Max-Age={SESSION_DAYS * 86400}", "HttpOnly", "SameSite=Lax"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie(*, secure: bool = False) -> str:
    parts = [f"{SESSION_COOKIE}=", "Path=/", "Max-Age=0", "HttpOnly", "SameSite=Lax"]
    if secure:
        parts.append("Secure")
    return "; ".join(parts)


def _validate(email: str, password: str, name: str) -> tuple[str, str, str]:
    email = (email or "").strip().lower()[:254]
    name = (name or "").strip()[:40] or "Student"
    if not _EMAIL.match(email):
        raise AuthError(400, "Enter a valid email address.")
    if len(password or "") < 8:
        raise AuthError(400, "Use at least 8 characters for your password.")
    if len(password) > 200:
        raise AuthError(400, "That password is too long.")
    return email, password, name


def signup(email: str, password: str, name: str, profile_id: str | None, remote: str = "") -> dict:
    email, password, name = _validate(email, password, name)
    _rate(f"{email}|{remote}")
    if _by_email(email):
        raise AuthError(409, "An account with that email already exists.")
    first = db.scalar("SELECT COUNT(*) FROM users", default=0) or 0
    user_id = secrets.token_hex(12)
    password_hash, salt = _hash(password)

    profile = profiles.get(profile_id) if profile_id else None
    if profile:
        age = int(profile["survey"].get("age") or 13)
        if age < 13:
            raise AuthError(403, "Email accounts are for ages 13 and up. Younger readers can keep using Pulse as a guest.")
    if profile and db.query_one("SELECT 1 FROM users WHERE profile_id=?", (profile["id"],)):
        profile = None
    if profile is None:
        profile = profiles.create(name)
    else:
        profile = profiles.update(profile["id"], name=name) or profile

    db.execute(
        """INSERT INTO users(id, email, name, password_hash, salt, is_admin, profile_id, created_at, last_login_at)
           VALUES(?,?,?,?,?,?,?,?,?)""",
        (user_id, email, name, password_hash, salt, 1 if int(first) == 0 else 0, profile["id"], iso(), iso()),
    )
    _rate_ok(f"{email}|{remote}")
    token = _create_session(user_id)
    user = _by_email(email)
    return {"account": public(user), "profile": profiles.get(profile["id"]), "token": token}


def login(email: str, password: str, remote: str = "") -> dict:
    email = (email or "").strip().lower()[:254]
    _rate(f"{email}|{remote}")
    user = _by_email(email)
    if not user or not _verify(password or "", user["password_hash"], user["salt"]):
        raise AuthError(401, "Email or password is incorrect.")
    db.execute("UPDATE users SET last_login_at=? WHERE id=?", (iso(), user["id"]))
    _rate_ok(f"{email}|{remote}")
    profile = profiles.get(user["profile_id"]) if user.get("profile_id") else None
    if profile is None:
        profile = profiles.create(user.get("name") or "Student")
        db.execute("UPDATE users SET profile_id=? WHERE id=?", (profile["id"], user["id"]))
    token = _create_session(user["id"])
    user = _by_email(email)
    return {"account": public(user), "profile": profile, "token": token}


def delete_account(user_id: str, password: str) -> str | None:
    user = db.query_one("SELECT * FROM users WHERE id=?", (user_id,))
    if not user or not _verify(password or "", user["password_hash"], user["salt"]):
        raise AuthError(401, "Password is incorrect.")
    profile_id = user["profile_id"]
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    if profile_id:
        profiles.delete(profile_id)
    return profile_id


def logout(request) -> None:
    token = session_token(request)
    if token:
        db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def link_profile(user_id: str, profile_id: str) -> None:
    db.execute("UPDATE users SET profile_id=? WHERE id=?", (profile_id, user_id))


def rename(user_id: str, name: str) -> None:
    name = " ".join(str(name or "").split())[:80] or "Student"
    db.execute("UPDATE users SET name=? WHERE id=?", (name, user_id))


def all_users() -> list[dict]:
    rows = db.query(
        """SELECT u.id, u.email, u.name, u.is_admin, u.profile_id, u.created_at, u.last_login_at,
                  p.name AS profile_name, p.onboarded, p.level, p.xp
           FROM users u LEFT JOIN profiles p ON p.id = u.profile_id
           ORDER BY u.created_at DESC"""
    )
    return [dict(row) for row in rows]


def users_csv() -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["email", "name", "admin", "profile_name", "onboarded", "level", "xp", "created_at", "last_login_at"])
    for user in all_users():
        writer.writerow([
            user["email"], user["name"] or "", "yes" if user["is_admin"] else "no",
            user["profile_name"] or "", "yes" if user["onboarded"] else "no",
            user["level"] or "", user["xp"] or "", user["created_at"] or "", user["last_login_at"] or "",
        ])
    return buffer.getvalue().encode("utf-8")
