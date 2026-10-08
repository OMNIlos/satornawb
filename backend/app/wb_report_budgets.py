"""Optional current budgets, independent of historical report completion.

One provider read per task, one delayed continuation at a time. No credentials
in broker arguments or persisted jobs; both cache and lease are connection-scoped.
"""
from copy import deepcopy
from hashlib import sha256
import time
from uuid import uuid4

from app.infra.redis_client import get_redis_client
from app.repricer_cache.store import get_source_cache, save_source_cache

TTL = 3600
LEASE = 1800
DEADLINE = 3600


def connection(token):
    return sha256(token.encode()).hexdigest()[:16]


def keys(org, digest):
    return f"ads_budgets_{digest}", f"ads_budget_job_{digest}", f"wb:optional-budgets:{org}:{digest}"


def recent(org, digest):
    cache_key, _, _ = keys(org, digest)
    entries = (get_source_cache(org, cache_key, slim=False) or {}).get("budgets", {})
    from datetime import datetime
    result = {}
    for campaign, entry in entries.items():
        try:
            age = time.time() - datetime.fromisoformat(entry["fetchedAt"].replace("Z", "+00:00")).timestamp()
            if 0 <= age < TTL and isinstance(entry.get("value"), dict) and entry['value'].get('totalKopecks') is not None:
                result[str(campaign)] = entry["value"]
        except (KeyError, TypeError, ValueError):
            continue
    return result


def public_job(job):
    return {key: job.get(key) for key in ("state", "collected", "total", "error", "updatedAt") if key in job}


def start(org, user, digest, campaign_ids, enqueue):
    ids = sorted({str(value) for value in campaign_ids if str(value).isdigit() and int(value) > 0})
    available = recent(org, digest)
    pending = [value for value in ids if value not in available]
    _, job_key, lock = keys(org, digest)
    if not pending:
        return {"state": "completed", "collected": len(ids), "total": len(ids)}
    redis = get_redis_client()
    owner = uuid4().hex
    if not redis.set(lock, owner, nx=True, ex=LEASE):
        return public_job(get_source_cache(org, job_key, slim=False) or {"state": "queued"})
    job = dict(owner=owner, state="queued", campaigns=pending, cursor=0, sequence=0, attempts=0,
               total=len(ids), collected=len(ids)-len(pending), deadline=time.time()+DEADLINE, updatedAt=time.time())
    try:
        save_source_cache(org, job_key, job, strict=True)
        enqueue(org, str(user), digest, owner, 0, 1)
    except Exception:
        job.update(state="failed", error="Не удалось поставить загрузку бюджетов в очередь")
        save_source_cache(org, job_key, job, strict=True)
        release(redis, lock, owner)
    return public_job(job)


def release(redis, lock, owner):
    redis.eval("if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('DEL',KEYS[1]) end return 0", 1, lock, owner)


def run_step(org, user, digest, owner, sequence, resolve_token, enqueue):
    cache_key, job_key, lock = keys(org, digest)
    redis = get_redis_client()
    # Claim this cursor atomically, including protection from duplicate delivery.
    step_lock = f"{lock}:step:{owner}:{sequence}"
    if not redis.set(step_lock, "1", nx=True, ex=600):
        return {"state": "duplicate"}
    try:
        job = get_source_cache(org, job_key, slim=False) or {}
        lease_owner = redis.get(lock)
        if isinstance(lease_owner, bytes):
            lease_owner = lease_owner.decode()
        if lease_owner != owner or job.get("owner") != owner or job.get("sequence") != sequence or job.get("state") not in {"queued", "running"}:
            return {"state": "superseded"}
        cursor = job["cursor"]
        def finish(state, error=None):
            job.update(state=state, updatedAt=time.time())
            if error:
                job["error"] = error
            save_source_cache(org, job_key, job, strict=True)
            release(redis, lock, owner)
            return public_job(job)
        if time.time() > job["deadline"]:
            return finish("failed", "Загрузка бюджетов превысила час; сохранённая часть доступна")
        token = resolve_token(org, user, None)
        if not token or connection(token) != digest:
            return finish("failed", "Подключение WB изменилось; бюджеты прежнего кабинета не используются")
        redis.eval("if redis.call('GET',KEYS[1]) == ARGV[1] then return redis.call('EXPIRE',KEYS[1],ARGV[2]) end return 0", 1, lock, owner, LEASE)
        from app.wb_api.ads_runtime import _normalize_budget, build_wb_ads_client
        from app.wb_api.client import RateLimitedWbApiClient, WbApiRequest
        from app.wb_api.report_reads import active_report_read, install_report_read
        ctx = install_report_read(org, token, job_key)
        try:
            client = RateLimitedWbApiClient(inner=build_wb_ads_client(scenario="complete", token_override=token))
            response = client.request(WbApiRequest(method="GET", path="/adv/v1/budget", query={"id": int(job["campaigns"][cursor])}))
        finally:
            active_report_read.reset(ctx)
        delay = 1
        if response.ok:
            from datetime import datetime, timezone
            value = _normalize_budget(response.data)
            if value.get('totalKopecks') is None:
                return finish('failed', 'WB вернул неполный бюджет. Историческая статистика сохранена')
            entries = (get_source_cache(org, cache_key, slim=False) or {}).get("budgets", {})
            entries[job["campaigns"][cursor]] = dict(value=value, fetchedAt=datetime.now(timezone.utc).isoformat())
            save_source_cache(org, cache_key, {"budgets": entries}, strict=True)
            job["collected"] += 1
            job["cursor"] += 1
            job["attempts"] = 0
        elif response.statusCode in {401, 403}:
            return finish("failed", f"Бюджеты недоступны: WB HTTP {response.statusCode}. Историческая статистика сохранена")
        elif response.statusCode == 429 or response.statusCode >= 500:
            job["attempts"] += 1
            retry_after = getattr(response.rateLimit, "retryAfterSeconds", None) or 60
            if job["attempts"] >= 3 or retry_after > 900:
                return finish("failed", f"Бюджеты временно недоступны: WB HTTP {response.statusCode}; сохранённая часть доступна")
            delay = max(20, retry_after)
        else:
            job["cursor"] += 1
            job["attempts"] = 0
            job["error"] = f"Часть бюджетов недоступна: WB HTTP {response.statusCode}"
        if job["cursor"] >= len(job["campaigns"]):
            return finish("completed" if job["collected"] == job["total"] else "failed")
        job.update(state="running", sequence=sequence+1, updatedAt=time.time())
        save_source_cache(org, job_key, job, strict=True)
        enqueue(org, user, digest, owner, sequence+1, delay)
        return public_job(job)
    except Exception:
        # Provider exception text may contain secrets. Never persist it.
        job = get_source_cache(org, job_key, slim=False) or {}
        if job.get("owner") == owner:
            job.update(state="failed", error="Не удалось загрузить бюджеты; историческая статистика сохранена", updatedAt=time.time())
            save_source_cache(org, job_key, job, strict=True)
            release(redis, lock, owner)
        return public_job(job)
    finally:
        redis.delete(step_lock)


def overlay(org, digest, report):
    """Read-time enrichment only; never alters historical metrics/cache freshness."""
    report = deepcopy(report)
    available = recent(org, digest)
    totals = {}
    for row in report.get("rows", []):
        value = available.get(str(row.get("campaignId")))
        for field, key in (("budgetCashKopecks", "cashKopecks"), ("budgetNettingKopecks", "nettingKopecks"), ("budgetTotalKopecks", "totalKopecks")):
            row[field] = value.get(key) if value else None
        if row.get("budgetTotalKopecks") is not None:
            totals[str(row["campaignId"])] = row["budgetTotalKopecks"]
    ids = {str(row.get("campaignId")) for row in report.get("rows", [])
           if str(row.get("campaignId")).isdigit() and int(row["campaignId"]) > 0}
    _, job_key, _ = keys(org, digest)
    job = public_job(get_source_cache(org, job_key, slim=False) or {"state": "idle"})
    if not ids:
        job = ({"state": "failed", "error": "Сохранённый отчёт не содержит ID кампаний WB; текущие бюджеты недоступны"}
               if report.get("rows") else {"state": "completed"})
    if ids and len(totals) == len(ids):
        job = {"state": "completed"}
    job.update(collected=len(totals), total=len(ids))
    report["budgetRefresh"] = job
    for kpi in report.get("kpis", []):
        if kpi.get("id") == "campaign_budget":
            kpi["value"] = str(sum(totals.values())) if ids and len(totals) == len(ids) else "—"
            kpi["hint"] = f"Текущие бюджеты: {len(totals)}/{len(ids)}. {job.get('error') or 'Загружаются отдельно от исторической статистики.'}"
    return report
