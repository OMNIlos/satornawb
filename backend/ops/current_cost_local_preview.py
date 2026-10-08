"""Isolated local UI/API preview. No workers or provider mutations.

Run from backend with the project's Python. Uses the existing development
schema bootstrap, not production migrations. Register a local account in UI.
Default denies all outbound traffic. --avito-readonly permits Avito OAuth and
explicit reads using credentials saved by the user, retaining preview.sqlite.
"""
from pathlib import Path
import os
import secrets
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
STATE = ROOT / ".local-preview"
STATE.mkdir(mode=0o700, exist_ok=True)
database_name = "wb-readonly.sqlite" if "--wb-readonly-data" in sys.argv else "preview.sqlite"
for name in list(os.environ):
    if name.startswith(("VELLA_", "WB_", "AVITO_", "CELERY_")):
        del os.environ[name]
os.environ.update(
    VELLA_ENV="local", VELLA_DATABASE_URL=f"sqlite+pysqlite:///{STATE / database_name}",
    VELLA_AUTH_SECRET=secrets.token_urlsafe(48), VELLA_AUTH_COOKIE_SECURE="false",
    VELLA_AUTH_COOKIE_SAMESITE="lax", VELLA_REPRICER_SCHEDULER_ENABLED="false",
    VELLA_WB_API_MODE="real",
    VELLA_AVITO_REPRICER_WORKER_ENABLED="false", VELLA_REAL_PRICE_APPLY_ENABLED="false",
    VELLA_REPRICER_LOCAL_PRICE_APPLY_ENABLED="false",
    VELLA_REDIS_URL="redis://127.0.0.1:59999/0",
    VELLA_CELERY_BROKER_URL="redis://127.0.0.1:59999/0",
    VELLA_CELERY_RESULT_BACKEND="redis://127.0.0.1:59999/1",
)
# This preview must never initiate provider traffic, even after an accidental
# button click. Listening and accepting localhost HTTP do not use connect().
def deny_connect(*args, **kwargs):
    raise OSError("External actions disabled in isolated local preview")
if "--wb-readonly" in sys.argv:
    from load_local_wb_readonly import install_readonly_network_guard, allowed_request as wb_read_allowed
    from local_avito_readonly import allowed_request as avito_read_allowed
    install_readonly_network_guard(socket.socket.connect, socket.socket.connect_ex,
        request_allowed=lambda request: wb_read_allowed(request) or ("--avito-readonly" in sys.argv and avito_read_allowed(request)),
        local_broker_port=59999 if "--report-queue" in sys.argv or "--report-worker" in sys.argv else None)
elif "--avito-readonly" in sys.argv:
    from load_local_wb_readonly import install_readonly_network_guard
    from local_avito_readonly import allowed_request
    install_readonly_network_guard(socket.socket.connect, socket.socket.connect_ex,
                                   request_allowed=allowed_request)
elif "--wb-readonly-data" in sys.argv:
    from load_local_wb_readonly import install_readonly_network_guard
    install_readonly_network_guard(socket.socket.connect, socket.socket.connect_ex)
else:
    socket.socket.connect = deny_connect
    socket.socket.connect_ex = deny_connect

from app.main import create_app
from app.infra.db import create_all_for_local_dev
from app.infra.models import Base
from datetime import timezone
from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator
import uvicorn

class PreviewUtcDateTime(TypeDecorator):
    """SQLite drops timezone metadata; PostgreSQL production does not."""
    impl = DateTime
    cache_ok = True

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value

for table in Base.metadata.tables.values():
    for column in table.columns:
        if isinstance(column.type, DateTime) and column.type.timezone:
            column.type = PreviewUtcDateTime(timezone=True)

app = create_app()
create_all_for_local_dev()
from local_wb_browser_prices import install_local_browser_price_storage
install_local_browser_price_storage()
if "--report-queue" in sys.argv or "--report-worker" in sys.argv:
    if "--wb-readonly" not in sys.argv:
        raise RuntimeError("Report queue requires the WB read-only guard")
    from app.infra.celery_app import celery_app
    celery_app.conf.task_routes = {**celery_app.conf.task_routes, **{
        name: {"queue": "satorna.local.readonly-reports"} for name in (
            "reports.build_report_for_org", "reports.build_digest_for_org", "reports.refresh_report_sources_for_org", "reports.refresh_budget_step")}}
if __name__ == "__main__":
    if "--report-worker" in sys.argv:
        celery_app.worker_main(["worker", "--pool=solo", "--concurrency=1", "--queues=satorna.local.readonly-reports", "--without-gossip", "--without-mingle", "--without-heartbeat", "--loglevel=WARNING"])
    else:
        uvicorn.run(app, host="127.0.0.1", port=58017, log_level="warning")
