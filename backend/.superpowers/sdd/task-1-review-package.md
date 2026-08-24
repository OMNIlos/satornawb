# Review Package Task 1
Base: 369a498
Head: f3f5766

## Commits
f3f5766 feat: add report data mart coverage reader

## Stat
 app/report_data_mart.py        | 176 +++++++++++++++++++++++++++++++++++++++++
 tests/test_report_data_mart.py |  54 +++++++++++++
 2 files changed, 230 insertions(+)

## Diff
diff --git a/app/report_data_mart.py b/app/report_data_mart.py
new file mode 100644
index 0000000..2d21a0b
--- /dev/null
+++ b/app/report_data_mart.py
@@ -0,0 +1,176 @@
+from __future__ import annotations
+
+from dataclasses import dataclass
+from datetime import date, datetime, timedelta, timezone
+from typing import Any, Callable, Iterable, Literal, Mapping
+
+from app.repricer_cache.store import get_source_cache
+
+SourceStatus = Literal["exact", "covering", "stale", "partial", "missing"]
+BundleStatus = Literal["covered", "partial", "source_cache_miss"]
+
+SOURCE_CACHE_TTL = timedelta(hours=24)
+
+
+@dataclass(frozen=True)
+class SourceCoverage:
+    source: str
+    source_key: str
+    status: SourceStatus
+    date_from: str | None = None
+    date_to: str | None = None
+    fetched_at: str | None = None
+    rows_count: int | None = None
+    error: str | None = None
+
+
+@dataclass(frozen=True)
+class ReportSourceBundle:
+    organization_id: int
+    date_from: date
+    date_to: date
+    status: BundleStatus
+    covered: bool
+    by_source: dict[str, SourceCoverage]
+    sources: dict[str, dict[str, Any]]
+    missing_sources: list[str]
+    sync_status: dict[str, Any]
+
+
+def _parse_date(value: Any) -> date | None:
+    if not value:
+        return None
+    try:
+        return date.fromisoformat(str(value)[:10])
+    except ValueError:
+        return None
+
+
+def _parse_datetime(value: Any) -> datetime | None:
+    if not value:
+        return None
+    try:
+        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
+    except ValueError:
+        return None
+    if parsed.tzinfo is None:
+        return parsed.replace(tzinfo=timezone.utc)
+    return parsed.astimezone(timezone.utc)
+
+
+def source_cache_matches_range(cache: Mapping[str, Any], date_from: date, date_to: date) -> bool:
+    return _parse_date(cache.get("dateFrom")) == date_from and _parse_date(cache.get("dateTo")) == date_to
+
+
+def source_cache_covers_range(cache: Mapping[str, Any], date_from: date, date_to: date) -> bool:
+    cached_from = _parse_date(cache.get("dateFrom"))
+    cached_to = _parse_date(cache.get("dateTo"))
+    return cached_from is not None and cached_to is not None and cached_from <= date_from and cached_to >= date_to
+
+
+def _is_stale(cache: Mapping[str, Any], *, now: datetime | None = None) -> bool:
+    fetched_at = _parse_datetime(cache.get("fetchedAt") or cache.get("finishedAt") or cache.get("completedAt"))
+    if fetched_at is None:
+        return False
+    current = now or datetime.now(timezone.utc)
+    return current - fetched_at > SOURCE_CACHE_TTL
+
+
+def _range_days(date_from: date, date_to: date) -> int:
+    return max(1, (date_to - date_from).days + 1)
+
+
+def _candidate_keys(source: str, date_from: date, date_to: date, sync_status: Mapping[str, Any]) -> list[str]:
+    days = _range_days(date_from, date_to)
+    keys: list[str] = []
+    suffix = str(sync_status.get("periodCacheSuffix") or "").strip()
+    if suffix:
+        keys.append(f"{source}_{suffix}")
+    keys.append(f"{source}_{days}")
+    keys.append(source)
+    return list(dict.fromkeys(keys))
+
+
+def _row_count(cache: Mapping[str, Any]) -> int | None:
+    raw_count = cache.get("count")
+    if isinstance(raw_count, int):
+        return raw_count
+    aggregates = cache.get("aggregates")
+    if isinstance(aggregates, dict):
+        return len(aggregates)
+    rows = cache.get("rows")
+    if isinstance(rows, list):
+        return len(rows)
+    return None
+
+
+def load_report_source_bundle(
+    *,
+    organization_id: int,
+    date_from: date,
+    date_to: date,
+    required_sources: Iterable[str],
+    get_cache: Callable[..., dict[str, Any] | None] = get_source_cache,
+) -> ReportSourceBundle:
+    sync_status = get_cache(organization_id, "wb_sync_status", slim=False) or {}
+    by_source: dict[str, SourceCoverage] = {}
+    sources: dict[str, dict[str, Any]] = {}
+    missing_sources: list[str] = []
+
+    for source in required_sources:
+        selected_key = source
+        selected_cache: dict[str, Any] | None = None
+        selected_status: SourceStatus = "missing"
+        for key in _candidate_keys(source, date_from, date_to, sync_status):
+            cache = get_cache(organization_id, key, slim=False) or {}
+            if not cache:
+                continue
+            selected_key = key
+            selected_cache = cache
+            if source_cache_matches_range(cache, date_from, date_to):
+                selected_status = "exact"
+                break
+            if source_cache_covers_range(cache, date_from, date_to):
+                selected_status = "covering"
+                break
+            selected_status = "partial"
+
+        if selected_cache is None:
+            missing_sources.append(source)
+            by_source[source] = SourceCoverage(source=source, source_key=selected_key, status="missing")
+            continue
+
+        if selected_status in {"exact", "covering"} and _is_stale(selected_cache):
+            selected_status = "stale"
+        sources[source] = selected_cache
+        by_source[source] = SourceCoverage(
+            source=source,
+            source_key=selected_key,
+            status=selected_status,
+            date_from=str(selected_cache.get("dateFrom")) if selected_cache.get("dateFrom") else None,
+            date_to=str(selected_cache.get("dateTo")) if selected_cache.get("dateTo") else None,
+            fetched_at=str(selected_cache.get("fetchedAt")) if selected_cache.get("fetchedAt") else None,
+            rows_count=_row_count(selected_cache),
+            error=str(selected_cache.get("error")) if selected_cache.get("error") else None,
+        )
+        if selected_status == "missing":
+            missing_sources.append(source)
+
+    if missing_sources:
+        status: BundleStatus = "source_cache_miss"
+    elif any(item.status in {"stale", "partial"} for item in by_source.values()):
+        status = "partial"
+    else:
+        status = "covered"
+
+    return ReportSourceBundle(
+        organization_id=organization_id,
+        date_from=date_from,
+        date_to=date_to,
+        status=status,
+        covered=status == "covered",
+        by_source=by_source,
+        sources=sources,
+        missing_sources=missing_sources,
+        sync_status=sync_status,
+    )
diff --git a/tests/test_report_data_mart.py b/tests/test_report_data_mart.py
new file mode 100644
index 0000000..aa45f17
--- /dev/null
+++ b/tests/test_report_data_mart.py
@@ -0,0 +1,54 @@
+from __future__ import annotations
+
+from datetime import date, datetime, timedelta, timezone
+
+from app.report_data_mart import (
+    load_report_source_bundle,
+    source_cache_covers_range,
+    source_cache_matches_range,
+)
+
+
+def test_source_cache_exact_and_covering_ranges():
+    exact = {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": datetime.now(timezone.utc).isoformat()}
+    covering = {"dateFrom": "2026-07-01", "dateTo": "2026-07-31", "fetchedAt": datetime.now(timezone.utc).isoformat()}
+
+    assert source_cache_matches_range(exact, date(2026, 7, 1), date(2026, 7, 7)) is True
+    assert source_cache_matches_range(covering, date(2026, 7, 3), date(2026, 7, 9)) is False
+    assert source_cache_covers_range(covering, date(2026, 7, 3), date(2026, 7, 9)) is True
+
+
+def test_load_report_source_bundle_reports_missing_and_stale_sources():
+    now = datetime.now(timezone.utc)
+    old = now - timedelta(days=3)
+    source_state = {
+        "finance_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": old.isoformat(), "aggregates": {"101": {"salesUnits": 2}}},
+        "ads_7": {"dateFrom": "2026-07-01", "dateTo": "2026-07-07", "fetchedAt": now.isoformat(), "aggregates": {"101": {"adSpendKopecks": 1200}}},
+        "wb_sync_status": {
+            "state": "completed",
+            "dateFrom": "2026-07-01",
+            "dateTo": "2026-07-07",
+            "periodDays": 7,
+            "periodCacheSuffix": "7",
+            "finishedAt": now.isoformat(),
+        },
+    }
+
+    def fake_get_cache(_organization_id: int, source_key: str, *, slim: bool = False):
+        return source_state.get(source_key)
+
+    bundle = load_report_source_bundle(
+        organization_id=1,
+        date_from=date(2026, 7, 1),
+        date_to=date(2026, 7, 7),
+        required_sources=["finance", "ads", "baskets"],
+        get_cache=fake_get_cache,
+    )
+
+    assert bundle.covered is False
+    assert bundle.status == "source_cache_miss"
+    assert bundle.by_source["finance"].status == "stale"
+    assert bundle.by_source["ads"].status == "exact"
+    assert bundle.by_source["baskets"].status == "missing"
+    assert bundle.missing_sources == ["baskets"]
+    assert bundle.sources["ads"]["aggregates"]["101"]["adSpendKopecks"] == 1200
