"""Accounts and sessions. Visitors get an automatic guest account (no sign-in, like a chat app): an opaque session
token in an HttpOnly cookie, stored hashed server-side. Password accounts (scrypt) are kept for a future sign-in
option. SQLite, separate from the CRM database."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_FAILURES, FAILURE_WINDOW_S = 5, 600
GUEST_DOMAIN = "@guest.local"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, company TEXT,
  pw_hash BLOB NOT NULL, salt BLOB NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), created_at TEXT NOT NULL, expires_at REAL NOT NULL);
"""


class AuthError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class User:
    id: str
    email: str
    name: str
    company: str | None
    created_at: str

    @property
    def is_guest(self) -> bool:
        return self.email.endswith(GUEST_DOMAIN)

    def public(self) -> dict:
        return {"id": self.id, "name": self.name, "guest": self.is_guest, "created_at": self.created_at,
                **({} if self.is_guest else {"email": self.email, "company": self.company})}


def _hash_pw(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthStore:
    def __init__(self, path: str | Path, session_days: int = 14):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()
        self.session_days = session_days
        self._failures: dict[str, list[float]] = {}

    @staticmethod
    def _user(row: sqlite3.Row | None) -> User | None:
        return User(row["id"], row["email"], row["name"], row["company"], row["created_at"]) if row else None

    def create_user(self, email: str, name: str, password: str, company: str | None = None) -> User:
        email = email.strip().lower()
        name = name.strip()
        if not EMAIL_RE.match(email) or len(email) > 200:
            raise AuthError("Enter a valid email address.")
        if not name or len(name) > 80:
            raise AuthError("Enter your name.")
        if len(password) < 8 or len(password) > 200:
            raise AuthError("Use a password with at least 8 characters.")
        salt = os.urandom(16)
        uid = "usr_" + secrets.token_hex(8)
        created = datetime.now(timezone.utc).isoformat()
        with self.lock:
            try:
                self.db.execute("INSERT INTO users(id, email, name, company, pw_hash, salt, created_at) VALUES(?,?,?,?,?,?,?)",
                                (uid, email, name, (company or "").strip()[:120] or None, _hash_pw(password, salt), salt, created))
                self.db.commit()
            except sqlite3.IntegrityError:
                raise AuthError("An account with this email already exists. Sign in instead.", 409)
        return User(uid, email, name, (company or "").strip()[:120] or None, created)

    def create_guest(self) -> User:
        """Anonymous account for a browser. It has no usable password; access is only through its session cookie."""
        uid = "usr_" + secrets.token_hex(8)
        salt = os.urandom(16)
        created = datetime.now(timezone.utc).isoformat()
        with self.lock:
            self.db.execute("INSERT INTO users(id, email, name, company, pw_hash, salt, created_at) VALUES(?,?,?,?,?,?,?)",
                            (uid, f"guest+{uid}{GUEST_DOMAIN}", "Guest", None, _hash_pw(secrets.token_urlsafe(24), salt), salt, created))
            self.db.commit()
        return User(uid, f"guest+{uid}{GUEST_DOMAIN}", "Guest", None, created)

    def _throttled(self, email: str) -> bool:
        now = time.time()
        recent = [t for t in self._failures.get(email, []) if now - t < FAILURE_WINDOW_S]
        self._failures[email] = recent
        return len(recent) >= MAX_FAILURES

    def authenticate(self, email: str, password: str) -> User:
        email = email.strip().lower()
        if self._throttled(email):
            raise AuthError("Too many attempts. Wait a few minutes and try again.", 429)
        with self.lock:
            row = self.db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        ok = bool(row) and hmac.compare_digest(_hash_pw(password, row["salt"]), row["pw_hash"])
        if not ok:
            self._failures.setdefault(email, []).append(time.time())
            raise AuthError("Email or password is incorrect.", 401)
        self._failures.pop(email, None)
        return self._user(row)  # type: ignore[return-value]

    def create_session(self, user_id: str, days: int | None = None) -> str:
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.db.execute("INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES(?,?,?,?)",
                            (_token_hash(token), user_id, datetime.now(timezone.utc).isoformat(),
                             time.time() + timedelta(days=days or self.session_days).total_seconds()))
            self.db.commit()
        return token

    def user_for_token(self, token: str | None) -> User | None:
        if not token:
            return None
        with self.lock:
            row = self.db.execute("SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash=?",
                                  (_token_hash(token),)).fetchone()
        if not row or row["expires_at"] < time.time():
            return None
        return self._user(row)

    def delete_session(self, token: str | None) -> None:
        if token:
            with self.lock:
                self.db.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))
                self.db.commit()
