"""Isolated local UI/API preview. No external network, workers or credentials.

Run from backend with the project's Python. Uses the existing development
schema bootstrap, not production migrations. Register a local account in UI.
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
)
# This preview must never initiate provider traffic, even after an accidental
# button click. Listening and accepting localhost HTTP do not use connect().
def deny_connect(*args, **kwargs):
    raise OSError("External actions disabled in isolated local preview")
if "--wb-readonly-data" in sys.argv:
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
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=58017, log_level="warning")
