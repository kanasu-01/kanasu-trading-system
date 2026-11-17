"""Protected Render-staging authentication and continuity metadata."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import threading
import time
from collections import deque
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, SecretStr

from core.staging import staging_enabled

PBKDF2_ITERATIONS = 600_000
SESSION_IDLE_SECONDS = 1800
SESSION_MAX_SECONDS = 28800
VERIFIER_ENV = "KANASU_STAGING_PASSWORD_VERIFIER"
ORIGINS_ENV = "KANASU_STAGING_ALLOWED_ORIGINS"
DEFAULT_ORIGIN = "https://kanasu-staging-frontend.onrender.com"
_RUNTIME_ID = secrets.token_urlsafe(18)
_RUNTIME_STARTED = datetime.now(timezone.utc).isoformat()


def _enc(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _dec(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)


def create_password_verifier(password: str, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or not 16 <= len(password) <= 4096:
        raise ValueError("Staging password must contain 16-4096 characters")
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_enc(salt)}${_enc(derived)}"


def _verifier() -> tuple[str, bytes, bytes]:
    encoded = os.getenv(VERIFIER_ENV)
    try:
        algorithm, rounds, salt, expected = (encoded or "").split("$")
        salt_b, expected_b = _dec(salt), _dec(expected)
        valid = (
            algorithm == "pbkdf2_sha256"
            and rounds == str(PBKDF2_ITERATIONS)
            and len(salt_b) >= 16
            and len(expected_b) == 32
            and _enc(salt_b) == salt
            and _enc(expected_b) == expected
        )
    except (ValueError, TypeError):
        valid = False
    if not valid or encoded is None:
        raise HTTPException(503, "Staging authentication unavailable")
    return encoded, salt_b, expected_b


class _Auth:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.sessions: dict[str, tuple[float, float, bytes]] = {}
        self.failures: dict[str, deque[float]] = {}
        self.global_failures: deque[float] = deque()
        self.verify_slots = threading.BoundedSemaphore(4)
        self.fingerprint: bytes | None = None

    def _sync(self, encoded: str) -> bytes:
        fingerprint = hashlib.sha256(encoded.encode()).digest()
        if self.fingerprint is not None and not hmac.compare_digest(self.fingerprint, fingerprint):
            self.sessions.clear()
        self.fingerprint = fingerprint
        return fingerprint

    def _prune(self, now: float) -> None:
        cutoff = now - 900
        while self.global_failures and self.global_failures[0] <= cutoff:
            self.global_failures.popleft()
        for source, failures in list(self.failures.items()):
            while failures and failures[0] <= cutoff:
                failures.popleft()
            if not failures:
                self.failures.pop(source, None)
        for key, (created, activity, _) in list(self.sessions.items()):
            if now - activity >= SESSION_IDLE_SECONDS or now - created >= SESSION_MAX_SECONDS:
                self.sessions.pop(key, None)

    def ready(self) -> None:
        _verifier()

    def login(self, password: str, source: str) -> str:
        encoded, salt, expected = _verifier()
        if not isinstance(password, str) or not password or len(password) > 4096:
            raise HTTPException(401, "Invalid staging credentials")
        source = (source or "unknown")[:256]
        with self.lock:
            now = time.monotonic(); self._prune(now); self._sync(encoded)
            bucket = self.failures.get(source, ())
            if len(bucket) >= 5 or len(self.global_failures) >= 100:
                raise HTTPException(429, "Too many login attempts")
        if not self.verify_slots.acquire(blocking=False):
            raise HTTPException(429, "Too many simultaneous login attempts")
        try:
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
        finally:
            self.verify_slots.release()
        with self.lock:
            now = time.monotonic(); self._prune(now)
            if os.getenv(VERIFIER_ENV) != encoded:
                raise HTTPException(503, "Staging authentication unavailable")
            fingerprint = self._sync(encoded)
            if not hmac.compare_digest(actual, expected):
                self.global_failures.append(now)
                if source not in self.failures and len(self.failures) >= 256:
                    raise HTTPException(429, "Too many login attempts")
                self.failures.setdefault(source, deque()).append(now)
                raise HTTPException(401, "Invalid staging credentials")
            if len(self.sessions) >= 32:
                raise HTTPException(429, "Too many active sessions")
            token = secrets.token_urlsafe(32)
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = (now, now, fingerprint)
            return token

    def authorize(self, token: str, *, refresh_activity: bool = True) -> None:
        encoded, _, _ = _verifier()
        key = hashlib.sha256((token or "").encode()).hexdigest()
        with self.lock:
            now = time.monotonic(); self._prune(now); fingerprint = self._sync(encoded)
            session = self.sessions.get(key)
            if session is None or not hmac.compare_digest(session[2], fingerprint):
                self.sessions.pop(key, None)
                raise HTTPException(401, "Login required")
            if refresh_activity:
                self.sessions[key] = (session[0], now, session[2])

    def logout(self, token: str) -> None:
        with self.lock:
            self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)


auth = _Auth()
bearer = HTTPBearer(auto_error=False)
router = APIRouter()


def _token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Login required")
    return credentials.credentials


def require_session(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    if staging_enabled():
        auth.authorize(_token(credentials))


def require_session_status(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    if staging_enabled():
        auth.authorize(_token(credentials), refresh_activity=False)


def runtime_metadata() -> dict[str, str]:
    return {"runtime_instance_id": _RUNTIME_ID, "runtime_started_at": _RUNTIME_STARTED, "storage_persistence": "ephemeral"}


def allowed_origins() -> list[str]:
    values = [x.strip() for x in os.getenv(ORIGINS_ENV, DEFAULT_ORIGIN).split(",") if x.strip()]
    if not values:
        raise RuntimeError("No staging browser origin configured")
    result: list[str] = []
    for value in values:
        parsed = urlsplit(value)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if (
            value == "*" or parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.path not in {"", "/"}
            or parsed.query or parsed.fragment or (parsed.scheme != "https" and not loopback)
        ):
            raise RuntimeError(f"Invalid staging browser origin: {value}")
        normalized = value.rstrip("/")
        if normalized not in result:
            result.append(normalized)
    return result


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: SecretStr


@router.post("/login")
async def login(request: Request, payload: Login) -> dict[str, object]:
    token = await run_in_threadpool(auth.login, payload.password.get_secret_value(), request.client.host if request.client else "unknown")
    return {"access_token": token, "token_type": "bearer", "idle_expires_in": SESSION_IDLE_SECONDS, "maximum_expires_in": SESSION_MAX_SECONDS, **runtime_metadata()}


@router.get("/session", dependencies=[Depends(require_session_status)])
async def session() -> dict[str, object]:
    return {"authenticated": True, **runtime_metadata()}


@router.post("/logout", dependencies=[Depends(require_session)])
async def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, bool]:
    auth.logout(_token(credentials))
    return {"signed_out": True}
