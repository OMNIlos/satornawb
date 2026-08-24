from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.config import get_settings, validate_security_settings
from app.contracts.envelopes import ErrorEnvelope, ErrorEnvelopeItem
from app.routers.account_health import router as account_health_router
from app.routers.avito_chats import router as avito_chats_router
from app.routers.avito_listings import router as avito_listings_router
from app.routers.avito_notifications import router as avito_notifications_router
from app.routers.avito_orders import router as avito_orders_router
from app.routers.avito_overview import router as avito_overview_router
from app.routers.avito_repricer import router as avito_repricer_router
from app.routers.avito_reviews import router as avito_reviews_router
from app.routers.avito_stats import router as avito_stats_router
from app.routers.auth import router as auth_router
from app.routers.cabinet import router as cabinet_router
from app.routers.control_plane import router as control_plane_router
from app.routers.notifications import router as notifications_router
from app.routers.one_c_cash_flow import router as one_c_cash_flow_router
from app.routers.source_registry import router as source_registry_router
from app.routers.wb_discovery import router as wb_discovery_router
from app.routers.wb_19_05 import router as wb_19_05_router
from app.routers.wb_reports_sprint_d import router as wb_reports_sprint_d_router
from app.routers.wb_reports_bff import router as wb_reports_bff_router
from app.routers.wb_reviews import router as wb_reviews_router
from app.routers.wb_repricer_bff import router as wb_repricer_bff_router
from app.routers.wb_repricer_sprint_b import router as wb_repricer_sprint_b_router
from app.routers.wb_repricer_sprint_c import router as wb_repricer_sprint_c_router
from app.routers.wb_repricer_wb23 import router as wb_repricer_wb23_router


def create_app() -> FastAPI:
    settings = get_settings()
    validate_security_settings(settings)
    app = FastAPI(
        title=settings.app_name,
        version=settings.contract_version,
        docs_url="/docs" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # The SKU list answers ~1.1 MB of JSON per page; uncompressed that is
    # seconds of transfer on a slow link even though the backend itself
    # responds in well under a second.
    app.add_middleware(
        GZipMiddleware,
        minimum_size=16 * 1024,
        compresslevel=4,
        thread_minimum_size=128 * 1024,
    )

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        code = f"HTTP_{exc.status_code}"
        message = str(exc.detail)
        details: dict[str, Any] = {}
        if isinstance(exc.detail, dict):
            raw_code = exc.detail.get("code")
            raw_message = exc.detail.get("message")
            raw_details = exc.detail.get("details")
            if isinstance(raw_code, str) and raw_code.strip():
                code = raw_code.strip()
            if isinstance(raw_message, str) and raw_message.strip():
                message = raw_message.strip()
            if isinstance(raw_details, dict):
                details = raw_details
        payload = ErrorEnvelope(
            error=ErrorEnvelopeItem(
                code=code,
                message=message,
                details=details,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
            headers=exc.headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        payload = ErrorEnvelope(
            error=ErrorEnvelopeItem(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"issues": exc.errors()},
            )
        )
        return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "environment": settings.environment,
            "contractVersion": settings.contract_version,
            "realPriceApplyEnabled": settings.real_price_apply_enabled,
            "repricerLocalPriceApplyEnabled": settings.repricer_local_price_apply_enabled,
            "repricerPreserveLocalPriceOverrides": settings.repricer_preserve_local_price_overrides,
            "legacyOneCEnabled": settings.one_c_enabled,
            "apiDocsEnabled": settings.api_docs_enabled,
            "infrastructure": {
                "databaseConfigured": bool(settings.database_url),
                "redisConfigured": bool(settings.redis_url),
                "celeryBrokerConfigured": bool(settings.celery_broker_url),
                "celeryResultBackendConfigured": bool(settings.celery_result_backend),
            },
        }

    app.include_router(auth_router)
    app.include_router(avito_chats_router)
    app.include_router(avito_listings_router)
    app.include_router(avito_notifications_router)
    app.include_router(avito_orders_router)
    app.include_router(avito_overview_router)
    app.include_router(avito_repricer_router)
    app.include_router(avito_reviews_router)
    app.include_router(avito_stats_router)
    app.include_router(cabinet_router)
    app.include_router(notifications_router)
    if settings.one_c_enabled:
        app.include_router(one_c_cash_flow_router)
    app.include_router(wb_reports_sprint_d_router)
    app.include_router(wb_reports_bff_router)
    app.include_router(wb_reviews_router)
    app.include_router(wb_19_05_router)
    app.include_router(account_health_router)
    app.include_router(control_plane_router)
    app.include_router(source_registry_router)
    app.include_router(wb_discovery_router)
    app.include_router(wb_repricer_bff_router)
    app.include_router(wb_repricer_wb23_router)
    app.include_router(wb_repricer_sprint_b_router)
    app.include_router(wb_repricer_sprint_c_router)
    return app


app = create_app()
