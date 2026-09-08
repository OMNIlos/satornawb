from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.cabinet.orm import LkOrganizationRow, LkUserRow, LkUserWbTokenRow
from app.config import get_settings
from app.infra.celery_app import get_celery_app
from app.infra.models import Base
from app.platform.integrations.orm import MarketplaceAccountRow


class _Lock:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired = acquired
        self.released = False

    def acquire(self, *, blocking: bool) -> bool:
        assert blocking is False
        return self.acquired

    def release(self) -> None:
        self.released = True


class _Redis:
    def __init__(self, lock: _Lock) -> None:
        self._lock = lock
        self.calls: list[tuple[str, int, bool]] = []

    def lock(self, name: str, *, timeout: int, blocking: bool) -> _Lock:
        self.calls.append((name, timeout, blocking))
        return self._lock


def _settings(*, enabled: bool = True, organizations: tuple[int, ...] = (2,)):
    return SimpleNamespace(
        canonical_shadow_collection_enabled=enabled,
        canonical_shadow_collection_organization_ids=organizations,
    )


def _bind_credential(monkeypatch, tasks) -> None:
    monkeypatch.setattr(
        tasks,
        "_bound_wb_credential",
        lambda _organization_id: (31, "lk_user_wb_tokens:21", "secret"),
    )


def test_shadow_schedule_is_disabled_by_default_and_parses_canary(monkeypatch):
    monkeypatch.delenv("VELLA_CANONICAL_SHADOW_COLLECTION_ENABLED", raising=False)
    monkeypatch.delenv(
        "VELLA_CANONICAL_SHADOW_COLLECTION_ORGANIZATION_IDS", raising=False
    )
    assert get_settings().canonical_shadow_collection_enabled is False
    get_celery_app.cache_clear()
    assert "canonical-collect-shadow-daily" not in get_celery_app().conf.beat_schedule

    monkeypatch.setenv("VELLA_CANONICAL_SHADOW_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("VELLA_CANONICAL_SHADOW_COLLECTION_ORGANIZATION_IDS", "2, 7")
    settings = get_settings()
    assert settings.canonical_shadow_collection_enabled is True
    assert settings.canonical_shadow_collection_organization_ids == (2, 7)

    get_celery_app.cache_clear()
    try:
        schedule = get_celery_app().conf.beat_schedule
        assert schedule["canonical-collect-shadow-daily"]["task"] == (
            "canonical.collect_shadow_all_orgs"
        )
        assert schedule["canonical-collect-shadow-daily"]["options"] == {
            "queue": "vella.canonical-shadow"
        }
        assert get_celery_app().conf.task_routes[
            "canonical.collect_shadow_for_org"
        ] == {"queue": "vella.canonical-shadow"}
    finally:
        get_celery_app.cache_clear()


def test_shadow_flag_reaches_worker_and_beat():
    compose = Path("docker-compose.yml").read_text()
    worker = compose.split("  worker:", 1)[1].split("  canonical-shadow-worker:", 1)[0]
    beat = compose.split("  beat:", 1)[1].split("volumes:", 1)[0]

    for service in (worker, beat):
        assert "VELLA_CANONICAL_SHADOW_COLLECTION_ENABLED" in service
        assert "VELLA_CANONICAL_SHADOW_COLLECTION_ORGANIZATION_IDS" in service

    dedicated = compose.split("  canonical-shadow-worker:", 1)[1].split("  beat:", 1)[0]
    assert "--queues=vella.canonical-shadow" in dedicated
    assert "--concurrency=1" in dedicated
    assert "--queues=vella.default" in worker


def test_dispatcher_enqueues_only_unique_positive_canary_orgs(monkeypatch):
    from app import canonical_shadow_tasks as tasks

    calls: list[tuple[tuple[int, str], dict[str, str]]] = []
    monkeypatch.setattr(
        tasks,
        "get_settings",
        lambda: _settings(organizations=(2, 2, -1, 7)),
    )
    monkeypatch.setattr(
        tasks.collect_canonical_shadow_for_org,
        "apply_async",
        lambda *, args, queue: (
            calls.append((args, {"queue": queue}))
            or SimpleNamespace(id=f"task-{args[0]}")
        ),
    )

    result = tasks.collect_canonical_shadow_all_orgs("2026-09-03")

    assert calls == [
        ((2, "2026-09-03"), {"queue": "vella.canonical-shadow"}),
        ((7, "2026-09-03"), {"queue": "vella.canonical-shadow"}),
    ]
    assert result == {
        "businessDate": "2026-09-03",
        "processedOrganizations": 2,
        "tasks": [
            {"organizationId": 2, "taskId": "task-2"},
            {"organizationId": 7, "taskId": "task-7"},
        ],
    }


def test_worker_rejects_disabled_or_unlisted_org_before_lock(monkeypatch):
    from app import canonical_shadow_tasks as tasks

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings(enabled=False))
    monkeypatch.setattr(
        tasks,
        "get_redis_client",
        lambda: (_ for _ in ()).throw(AssertionError("redis must not be touched")),
    )
    assert tasks.collect_canonical_shadow_for_org(2, "2020-01-01") == {
        "organizationId": 2,
        "skipped": True,
        "reason": "canonical_shadow_disabled",
    }

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings(organizations=(7,)))
    assert tasks.collect_canonical_shadow_for_org(2, "2020-01-01") == {
        "organizationId": 2,
        "skipped": True,
        "reason": "organization_not_enabled",
    }

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings())
    assert tasks.collect_canonical_shadow_for_org(2, 123) == {
        "organizationId": 2,
        "state": "failed",
        "errorCode": "invalid_business_date",
    }


def test_worker_retries_lock_failure_without_leaking_error(monkeypatch):
    from app import canonical_shadow_tasks as tasks

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings())
    monkeypatch.setattr(
        tasks,
        "get_redis_client",
        lambda: (_ for _ in ()).throw(RuntimeError("secret-redis-detail")),
    )
    retries = []
    monkeypatch.setattr(
        tasks.collect_canonical_shadow_for_org,
        "retry",
        lambda **kwargs: retries.append(kwargs) or {"retry": True},
    )

    assert tasks.collect_canonical_shadow_for_org(2, "2020-01-01") == {"retry": True}
    assert str(retries[0]["exc"]) == "canonical_shadow_lock_unavailable"
    assert retries[0]["countdown"] == 1800
    assert "secret-redis-detail" not in str(retries)


def test_worker_serializes_and_returns_only_safe_evidence(monkeypatch):
    from app import canonical_shadow_tasks as tasks

    lock = _Lock()
    redis = _Redis(lock)
    periods = []
    monkeypatch.setattr(tasks, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks, "get_redis_client", lambda: redis)
    _bind_credential(monkeypatch, tasks)

    def advertising(organization_id, period, **credentials):
        periods.append(("advertising", organization_id, period, credentials))
        return {
            "state": "ready",
            "syncRunId": "ads-run",
            "snapshotChecksum": "ads-checksum",
            "factCount": 10,
            "campaignCount": 3,
            "expectedRequests": 4,
            "completedRequests": 4,
            "sourceTotalSpendKopecks": 1234,
        }

    def funnel(organization_id, period, **credentials):
        periods.append(("funnel", organization_id, period, credentials))
        return {
            "state": "ready",
            "syncRunId": "funnel-run",
            "snapshotChecksum": "funnel-checksum",
            "factCount": 20,
            "expectedRequests": 2,
            "completedRequests": 2,
            "marketplaceAccountId": 99,
        }

    monkeypatch.setattr(tasks, "backfill_raw_advertising", advertising)
    monkeypatch.setattr(tasks, "backfill_raw_funnel", funnel)

    result = tasks.collect_canonical_shadow_for_org(2, "2020-01-01")

    assert [
        (kind, org, period.cache_key, credentials)
        for kind, org, period, credentials in periods
    ] == [
        (
            "advertising",
            2,
            "2020-01-01_2020-01-01",
            {
                "marketplace_account_id": 31,
                "credential_ref": "lk_user_wb_tokens:21",
                "wb_token": "secret",
            },
        ),
        (
            "funnel",
            2,
            "2020-01-01_2020-01-01",
            {
                "marketplace_account_id": 31,
                "credential_ref": "lk_user_wb_tokens:21",
                "wb_token": "secret",
            },
        ),
    ]
    assert redis.calls == [("satorna:canonical-shadow:2", 21_600, False)]
    assert lock.released is True
    assert result == {
        "organizationId": 2,
        "businessDate": "2020-01-01",
        "state": "ready",
        "advertising": {
            "state": "ready",
            "syncRunId": "ads-run",
            "snapshotChecksum": "ads-checksum",
            "factCount": 10,
            "campaignCount": 3,
            "expectedRequests": 4,
            "completedRequests": 4,
        },
        "funnel": {
            "state": "ready",
            "syncRunId": "funnel-run",
            "snapshotChecksum": "funnel-checksum",
            "factCount": 20,
            "expectedRequests": 2,
            "completedRequests": 2,
        },
    }


def test_worker_skips_contended_lock_and_isolates_domain_failure(monkeypatch):
    from app import canonical_shadow_tasks as tasks

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks, "get_redis_client", lambda: _Redis(_Lock(False)))
    monkeypatch.setattr(
        tasks,
        "backfill_raw_advertising",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    monkeypatch.setattr(
        tasks,
        "backfill_raw_funnel",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    assert tasks.collect_canonical_shadow_for_org(2, "2020-01-01") == {
        "organizationId": 2,
        "businessDate": "2020-01-01",
        "skipped": True,
        "reason": "collection_in_progress",
    }

    lock = _Lock()
    monkeypatch.setattr(tasks, "get_redis_client", lambda: _Redis(lock))
    _bind_credential(monkeypatch, tasks)
    calls = []

    def fail_advertising(*_args, **_kwargs):
        calls.append("advertising")
        raise RuntimeError("secret-token")

    monkeypatch.setattr(
        tasks,
        "backfill_raw_advertising",
        fail_advertising,
    )
    monkeypatch.setattr(
        tasks,
        "backfill_raw_funnel",
        lambda *_args, **_kwargs: (
            calls.append("funnel") or {"state": "ready", "factCount": 1}
        ),
    )
    retries = []
    monkeypatch.setattr(
        tasks.collect_canonical_shadow_for_org,
        "retry",
        lambda **kwargs: retries.append(kwargs) or {"retry": True},
    )

    result = tasks.collect_canonical_shadow_for_org(2, "2020-01-01")

    assert result == {"retry": True}
    assert len(retries) == 1
    assert retries[0]["countdown"] == 1800
    assert str(retries[0]["exc"]) == "canonical_shadow_incomplete"
    assert "secret-token" not in str(retries)
    assert calls == ["advertising", "funnel"]
    assert lock.released is True


def test_worker_fails_closed_on_invalid_backfill_result(monkeypatch):
    from app import canonical_shadow_tasks as tasks

    monkeypatch.setattr(tasks, "get_settings", lambda: _settings())
    monkeypatch.setattr(tasks, "get_redis_client", lambda: _Redis(_Lock()))
    _bind_credential(monkeypatch, tasks)
    calls = []
    monkeypatch.setattr(
        tasks, "backfill_raw_advertising", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(
        tasks,
        "backfill_raw_funnel",
        lambda *_args, **_kwargs: (
            calls.append("funnel") or {"state": "ready", "factCount": 1}
        ),
    )
    monkeypatch.setattr(
        tasks.collect_canonical_shadow_for_org,
        "retry",
        lambda **_kwargs: {"retry": True},
    )

    result = tasks.collect_canonical_shadow_for_org(2, "2020-01-01")

    assert result == {"retry": True}
    assert calls == ["funnel"]


def test_bound_credential_rejects_cross_organization_token(monkeypatch):
    from app import canonical_shadow_tasks as tasks

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime(2026, 9, 4, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add_all(
            [
                LkOrganizationRow(organization_id=2, slug="two", name="Two"),
                LkOrganizationRow(organization_id=3, slug="three", name="Three"),
                LkUserRow(
                    user_id="user-two",
                    organization_id=2,
                    email="two@example.com",
                    password_hash="unused",
                    full_name="Two",
                    permission_profile="admin",
                    is_active=True,
                ),
                LkUserRow(
                    user_id="user-three",
                    organization_id=3,
                    email="three@example.com",
                    password_hash="unused",
                    full_name="Three",
                    permission_profile="admin",
                    is_active=True,
                ),
                LkUserWbTokenRow(
                    token_id=21,
                    user_id="user-two",
                    organization_id=2,
                    wb_token="  bound-secret  ",
                    token_masked="***",
                ),
                LkUserWbTokenRow(
                    token_id=22,
                    user_id="user-three",
                    organization_id=3,
                    wb_token="other-secret",
                    token_masked="***",
                ),
                MarketplaceAccountRow(
                    marketplace_account_id=31,
                    organization_id=2,
                    marketplace="wb",
                    external_account_id="cabinet-two",
                    status="connected",
                    credential_ref="lk_user_wb_tokens:21",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

    monkeypatch.setattr(tasks, "get_session_factory", lambda: factory)
    assert tasks._bound_wb_credential(2) == (
        31,
        "lk_user_wb_tokens:21",
        "bound-secret",
    )

    with Session(engine) as session:
        account = session.get(MarketplaceAccountRow, 31)
        assert account is not None
        account.credential_ref = "lk_user_wb_tokens:22"
        session.commit()

    with pytest.raises(tasks.CanonicalShadowCredentialError) as raised:
        tasks._bound_wb_credential(2)
    assert raised.value.error_code == "wb_credential_binding_invalid"
    assert "secret" not in str(raised.value)

    with Session(engine) as session:
        account = session.get(MarketplaceAccountRow, 31)
        assert account is not None
        account.credential_ref = None
        session.commit()
    with pytest.raises(tasks.CanonicalShadowCredentialError):
        tasks._bound_wb_credential(2)
