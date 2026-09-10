"""Linux VM keeps native live flags but uses peer-auth DB and private Redis IPC."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url


def launcher():
    path = Path(__file__).resolve().parents[1] / "ops/wb_live_linux.py"
    spec = importlib.util.spec_from_file_location("satorna_linux_launcher_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("kind,role", [("api", "wb_live_api"), ("worker", "wb_live_worker"), ("beat", "wb_live_dispatch")])
def test_runtime_has_no_owner_db_role_or_tcp_broker_and_external_writes_stay_off(kind, role):
    module = launcher()
    env = module.service_environment(kind, "synthetic-auth-secret")
    url = make_url(env["VELLA_DATABASE_URL"])
    assert url.username == role and url.database == "satorna_wb_live"
    assert url.password is None and url.host is None
    assert env["VELLA_REDIS_URL"] == "unix:///run/redis/redis-server.sock?db=0"
    assert env["VELLA_CELERY_BROKER_URL"] == "redis+socket:///run/redis/redis-server.sock?virtual_host=0"
    assert env["VELLA_CELERY_RESULT_BACKEND"] == env["VELLA_CELERY_BROKER_URL"]
    assert env["VELLA_WB_LIVE_SYNC_ENABLED"] == "true"
    assert env["VELLA_WB_API_MODE"] == "real"
    for name in ("REAL_PRICE_APPLY_ENABLED", "REPRICER_LOCAL_PRICE_APPLY_ENABLED", "REPRICER_SCHEDULER_ENABLED", "AVITO_REPRICER_PRICE_APPLY_ENABLED", "WB_FEEDBACKS_SEND_ENABLED", "CANONICAL_SHADOW_COLLECTION_ENABLED"):
        assert env["VELLA_" + name] == "false"
    if kind == "beat":
        assert "VELLA_MARKETPLACE_CREDENTIAL_KEYRING_DIR" not in env
    else:
        assert env["VELLA_MARKETPLACE_CREDENTIAL_KEYRING_DIR"] == "/var/lib/satorna-wb-live/keyring"


@pytest.mark.parametrize("kind", ["owner", "redis", "", "API", None])
def test_unknown_role_is_rejected_before_environment_construction(kind):
    with pytest.raises(ValueError, match="WB_LOCAL_ROLE_INVALID"):
        launcher().service_environment(kind, "synthetic-auth-secret")


@pytest.mark.parametrize("secret", ["", "bad\nInjected=value", "bad\rvalue", None])
def test_environment_file_injection_is_rejected(secret):
    with pytest.raises(ValueError, match="WB_LOCAL_AUTH_INVALID"):
        launcher().service_environment("api", secret)
