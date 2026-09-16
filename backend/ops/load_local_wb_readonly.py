"""Explicit one-shot WB read into the existing cache; API remains network-disabled.

No scheduler, price writes, synthetic financial policies or demo catalog copied.
Run from backend: ../.venv/bin/python ops/load_local_wb_readonly.py --org ID
"""
import argparse
import fcntl
import logging
import os
import socket
import sqlite3
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


ALLOWED = {
    ("GET", "discounts-prices-api.wildberries.ru", "/api/v2/list/goods/filter"),
    ("POST", "discounts-prices-api.wildberries.ru", "/api/v2/list/goods/filter"),
    ("POST", "content-api.wildberries.ru", "/content/v2/get/cards/list"),
    ("GET", "common-api.wildberries.ru", "/api/v1/tariffs/commission"),
    ("POST", "seller-analytics-api.wildberries.ru", "/api/analytics/v1/stocks-report/wb-warehouses"),
    ("POST", "seller-analytics-api.wildberries.ru", "/api/v2/stocks-report/products/products"),
    ("GET", "statistics-api.wildberries.ru", "/api/v1/supplier/orders"),
    ("GET", "statistics-api.wildberries.ru", "/api/v1/supplier/sales"),
    ("POST", "finance-api.wildberries.ru", "/api/finance/v1/sales-reports/detailed"),
}


def allowed_request(request):
    return (request.url.scheme == "https" and request.url.port in (None, 443)
            and (request.method, request.url.host, request.url.path) in ALLOWED)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", type=int, required=True)
    parser.add_argument("--sources", default="goods,content,stocks,period-stats,finance")
    args = parser.parse_args()
    sources = args.sources.split(",")
    if not set(sources) <= {"goods", "content", "stocks", "period-stats", "finance"}:
        raise SystemExit("Unsupported source")
    os.umask(0o077)
    original_connect, original_connect_ex = socket.socket.connect, socket.socket.connect_ex
    sys.argv.append("--wb-readonly-data")
    import current_cost_local_preview as preview
    lock = (preview.STATE / "wb-readonly-load.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Only the one-shot collector permits outbound HTTP. The serving process
    # continues to deny all outbound sockets, including price application.
    import httpx
    original_send = httpx.Client.send
    def guarded_send(client, request, **kwargs):
        if not allowed_request(request):
            raise RuntimeError("LOCAL_WB_READ_ENDPOINT_NOT_ALLOWED")
        kwargs["follow_redirects"] = False
        return original_send(client, request, **kwargs)
    httpx.Client.send = guarded_send
    socket.socket.connect, socket.socket.connect_ex = original_connect, original_connect_ex
    logging.disable(logging.CRITICAL)  # Never print upstream payloads or secrets.

    source = preview.STATE / "preview.sqlite"
    target = preview.STATE / "wb-readonly.sqlite"
    with sqlite3.connect(f"file:{target}?mode=rw", uri=True) as db:
        db.execute("ATTACH DATABASE ? AS original", (f"file:{source}?mode=ro",))
        present = db.execute("SELECT count(*) FROM lk_organizations").fetchone()[0]
        if not present:
            # Copy authentication only. Never copy demo costs, policies, goods,
            # financial facts, mappings, assignments or connected demo account.
            for table in ("lk_organizations", "lk_users", "iam_memberships", "lk_user_wb_tokens"):
                db.execute(f"INSERT INTO main.{table} SELECT * FROM original.{table} WHERE organization_id=?", (args.org,))
            for table in ("lk_user_permissions", "lk_sessions"):
                db.execute(f"INSERT INTO main.{table} SELECT * FROM original.{table} WHERE user_id IN (SELECT user_id FROM main.lk_users)")
        tokens = db.execute("SELECT wb_token FROM lk_user_wb_tokens WHERE organization_id=?", (args.org,)).fetchall()
        if len(tokens) != 1 or not tokens[0][0]:
            raise RuntimeError("EXPECTED_ONE_SAVED_WB_TOKEN")
    from app.repricer_sync import refresh_wb_data_sources
    yesterday = datetime.now(ZoneInfo("Europe/Moscow")).date() - timedelta(days=1)
    result = refresh_wb_data_sources(
        organization_id=args.org, wb_token=tokens[0][0], period_days=7,
        date_from=yesterday-timedelta(days=6), date_to=yesterday,
        sources=sources, force=True, _parallelize=False,
    )
    print({"state": result.get("state"), "steps": [
        {key: step.get(key) for key in ("source", "status", "count")}
        for step in result.get("steps", [])]}, flush=True)
    lock.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print({"error_type": type(exc).__name__}, flush=True)
        raise SystemExit(1) from None
