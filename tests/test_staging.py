from __future__ import annotations

import importlib.util
import io
import logging
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException

import api.staging as staging
import core.staging as safety

PASSWORD = "sixteen-plus-chars-for-staging"


def status(exc: pytest.ExceptionInfo[HTTPException], expected: int) -> None:
    assert exc.value.status_code == expected


def test_auth_verifier_session_rotation_logout_and_limits(monkeypatch):
    verifier = staging.create_password_verifier(PASSWORD, b"0123456789abcdef")
    assert PASSWORD not in verifier
    monkeypatch.setenv(staging.VERIFIER_ENV, verifier)
    auth = staging._Auth()

    with pytest.raises(HTTPException) as exc:
        auth.login("wrong-password", "host")
    status(exc, 401)

    token = auth.login(PASSWORD, "host")
    auth.authorize(token)
    assert token not in auth.sessions
    auth.logout(token)
    with pytest.raises(HTTPException) as exc:
        auth.authorize(token)
    status(exc, 401)

    token = auth.login(PASSWORD, "host")
    monkeypatch.setenv(staging.VERIFIER_ENV, staging.create_password_verifier("new-password-long-enough", b"abcdefgh01234567"))
    with pytest.raises(HTTPException) as exc:
        auth.authorize(token)
    status(exc, 401)


def test_auth_missing_verifier_rate_limit_and_capacity(monkeypatch):
    monkeypatch.delenv(staging.VERIFIER_ENV, raising=False)
    with pytest.raises(HTTPException) as exc:
        staging._Auth().login(PASSWORD, "host")
    status(exc, 503)

    monkeypatch.setenv(staging.VERIFIER_ENV, staging.create_password_verifier(PASSWORD, b"0123456789abcdef"))
    auth = staging._Auth()
    for _ in range(5):
        with pytest.raises(HTTPException) as exc:
            auth.login("wrong-password", "host")
        status(exc, 401)
    with pytest.raises(HTTPException) as exc:
        auth.login(PASSWORD, "host")
    status(exc, 429)

    auth = staging._Auth()
    for index in range(32):
        auth.login(PASSWORD, f"host-{index}")
    with pytest.raises(HTTPException) as exc:
        auth.login(PASSWORD, "host-overflow")
    status(exc, 429)



def test_session_idle_and_maximum_expiry(monkeypatch):
    monkeypatch.setenv(staging.VERIFIER_ENV, staging.create_password_verifier(PASSWORD, b"0123456789abcdef"))
    clock = {"now": 1000.0}
    monkeypatch.setattr(staging.time, "monotonic", lambda: clock["now"])
    auth = staging._Auth()
    token = auth.login(PASSWORD, "host")
    clock["now"] += staging.SESSION_IDLE_SECONDS + 1
    with pytest.raises(HTTPException) as exc:
        auth.authorize(token)
    status(exc, 401)

    token = auth.login(PASSWORD, "host")
    created = clock["now"]
    while clock["now"] - created < staging.SESSION_MAX_SECONDS:
        clock["now"] += staging.SESSION_IDLE_SECONDS - 1
        if clock["now"] - created >= staging.SESSION_MAX_SECONDS:
            break
        auth.authorize(token)
    clock["now"] = created + staging.SESSION_MAX_SECONDS + 1
    with pytest.raises(HTTPException) as exc:
        auth.authorize(token)
    status(exc, 401)

def test_session_status_check_does_not_refresh_idle_activity(monkeypatch):
    monkeypatch.setenv(staging.VERIFIER_ENV, staging.create_password_verifier(PASSWORD, b"0123456789abcdef"))
    clock = {"now": 1000.0}
    monkeypatch.setattr(staging.time, "monotonic", lambda: clock["now"])
    auth = staging._Auth()
    token = auth.login(PASSWORD, "host")
    clock["now"] += staging.SESSION_IDLE_SECONDS - 1
    auth.authorize(token, refresh_activity=False)
    clock["now"] += 2
    with pytest.raises(HTTPException) as exc:
        auth.authorize(token, refresh_activity=False)
    status(exc, 401)


def test_staging_boundary_and_sdk_logger_guard(monkeypatch):
    monkeypatch.setenv("KANASU_STAGING_MODE", "true")
    assert safety.staging_enabled()
    secret = RuntimeError("SECRET_PROVIDER_TEXT")
    assert str(safety.safe_failure(secret, "withheld")) == "withheld"

    logger = logging.getLogger("synthetic-smartapi")
    logger.disabled = False
    capture = io.StringIO(); logger.addHandler(logging.StreamHandler(capture))
    fake_sdk = types.ModuleType("SmartApi")
    fake_http = types.ModuleType("SmartApi.smartConnect")
    fake_ws = types.ModuleType("SmartApi.smartWebSocketV2")
    fake_http.logger = logger; fake_http.log = logger; fake_ws.logger = logger
    FakeConnect = type("SmartConnect", (), {}); FakeConnect.__module__ = "SmartApi.smartConnect"
    fake_sdk.SmartConnect = FakeConnect
    monkeypatch.setitem(sys.modules, "SmartApi", fake_sdk)
    monkeypatch.setitem(sys.modules, "SmartApi.smartConnect", fake_http)
    monkeypatch.setitem(sys.modules, "SmartApi.smartWebSocketV2", fake_ws)
    safety.disable_smartapi_logging()
    logger.error("SECRET_PROVIDER_TEXT")
    assert "SECRET_PROVIDER_TEXT" not in capture.getvalue()


def _deploy_module():
    path = Path(__file__).parents[1] / "scripts" / "render_deploy.py"
    spec = importlib.util.spec_from_file_location("render_deploy", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_render_deploy_pins_sha_and_rejects_wrong_url(monkeypatch):
    deploy = _deploy_module()
    seen = []

    def fake_request(method, path, _token, body=None):
        seen.append((method, path, body))
        if method == "POST":
            return 201, {"id": "dep-1", "commit": {"id": "a" * 40}}
        raise AssertionError((method, path))

    monkeypatch.setattr(deploy, "request", fake_request)
    assert deploy.deploy("token", "srv-1", "a" * 40) == "dep-1"
    assert seen[0][2]["commitId"] == "a" * 40

    def wrong_url(method, path, _token, body=None):
        return 200, [{"service": {"name": deploy.FRONTEND_NAME, "id": "srv", "ownerId": deploy.WORKSPACE, "type": "static_site", "repo": deploy.REPO, "branch": deploy.BRANCH, "autoDeployTrigger": "off", "suspended": "not_suspended", "serviceDetails": {"url": "https://wrong.onrender.com"}}}]

    monkeypatch.setattr(deploy, "request", wrong_url)
    with pytest.raises(deploy.DeployError):
        deploy.service("token", deploy.FRONTEND_NAME, "static_site", deploy.FRONTEND_URL)


def test_render_commands_force_staging_safety():
    deploy = _deploy_module()
    assert "ENABLE_LIVE_TRADING=false" in deploy.BACKEND_START
    assert "PAPER_DATA_SOURCE=ANGELONE" in deploy.BACKEND_START
    assert "--workers 1" in deploy.BACKEND_START
    assert deploy.FRONTEND_URL in deploy.BACKEND_START
    assert "export VITE_KANASU_STAGING_AUTH=true" in deploy.FRONTEND_BUILD
    assert f"export VITE_API_BASE_URL={deploy.BACKEND_URL}/api" in deploy.FRONTEND_BUILD
    assert deploy.FRONTEND_BUILD.index("export VITE_KANASU_STAGING_AUTH=true") < deploy.FRONTEND_BUILD.index("npm ci")
    assert deploy.FRONTEND_BUILD.index(f"export VITE_API_BASE_URL={deploy.BACKEND_URL}/api") < deploy.FRONTEND_BUILD.index("npm run build")


def test_broker_login_failure_hides_secret_in_staging(monkeypatch, caplog):
    from types import SimpleNamespace
    import traceback
    import core.broker.angelone as module
    from core.broker.angelone_config import AngelOneConfig

    monkeypatch.setenv("RENDER", "true")
    secret = "SYNTHETIC_SECRET_DO_NOT_LOG"
    class FakeSmartConnect:
        def __init__(self, api_key): self.api_key = api_key
        def generateSession(self, client_id, pin, totp):
            raise RuntimeError(f"provider rejected {self.api_key} {client_id} {pin} {totp} {secret}")
    monkeypatch.setattr(module, "SmartConnect", FakeSmartConnect)
    monkeypatch.setattr(module.pyotp, "TOTP", lambda _secret: SimpleNamespace(now=lambda: "739281"))
    broker = module.AngelOneBroker(AngelOneConfig(api_key=secret, client_id="client", client_pin="pin", totp_secret="totp"), paper_mode=True, login_retry_attempts=1, login_retry_delay_seconds=0)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="AngelOne login request failed") as exc:
            broker.login()
    assert secret not in caplog.text
    assert secret not in "".join(traceback.format_exception(exc.value))


def test_websocket_transport_hides_token_and_keeps_connection_class(monkeypatch):
    import traceback
    from core.broker.angelone_config import AngelOneConfig
    from core.market_data.angelone_live_market_data import AngelOneLiveMarketDataAdapter

    monkeypatch.setenv("RENDER", "true")
    secret = "SYNTHETIC_BEARER_TOKEN_DO_NOT_LOG"
    class FailingSocket:
        def __init__(self, *_args, **_kwargs): pass
        def connect(self): raise ConnectionError(f"provider refused {secret}")
    adapter = AngelOneLiveMarketDataAdapter(
        config=AngelOneConfig(api_key="api", client_id="client", client_pin="pin", symbol_token_map={"RELIANCE": "2885"}),
        auth_token=secret, feed_token="feed", symbol="RELIANCE", on_update=lambda _x: None, websocket_factory=FailingSocket,
    )
    with pytest.raises(ConnectionError, match="AngelOne market-data connection failed") as exc:
        adapter.connect()
    assert secret not in "".join(traceback.format_exception(exc.value))


def test_paper_runtime_failure_is_sanitized_only_in_staging(monkeypatch, caplog):
    import threading
    import traceback
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from core.runtime.paper_runtime import execute_prepared_live_paper_trading

    class Session:
        symbol = "RELIANCE"
        def __init__(self): self.failure_message = None
        def start(self): pass
        def fail(self, failure): self.failure_message = str(failure)
    class Runtime:
        def run_until(self, **_kwargs): raise ConnectionError("provider secret SECRET_123")
    session = Session()
    prepared = SimpleNamespace(session=session, state_lock=threading.RLock(), runtime=Runtime(), session_end=datetime.now(timezone.utc), now=lambda: datetime.now(timezone.utc), clock_interval_seconds=0.01)
    monkeypatch.setenv("RENDER", "true")
    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="provider details are withheld") as exc:
            execute_prepared_live_paper_trading(prepared)
    assert "SECRET_123" not in (session.failure_message or "")
    assert "SECRET_123" not in caplog.text
    assert "SECRET_123" not in "".join(traceback.format_exception(exc.value))
