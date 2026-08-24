from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.cabinet.schemas import LoginRequest, LoginResponse, RefreshResponse, RegisterRequest, RegisterResponse
from app.cabinet.store import build_cabinet_me
from app.config import get_settings
from app.contracts.envelopes import DataEnvelope
from app.control_plane.auth import actor_from_request, login_with_email_password, logout_current_session, refresh_access_token, register_with_email_password


router = APIRouter(tags=["auth"])


def _ip_from_request(request: Request) -> str | None:
    return request.client.host if request.client else None


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    settings = get_settings()
    secure = settings.auth_cookie_secure or settings.auth_cookie_samesite == "none"
    response.set_cookie(
        key=settings.auth_refresh_cookie_name,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
        max_age=settings.auth_refresh_ttl_seconds,
        domain=settings.auth_cookie_domain,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    secure = settings.auth_cookie_secure or settings.auth_cookie_samesite == "none"
    response.delete_cookie(
        key=settings.auth_refresh_cookie_name,
        domain=settings.auth_cookie_domain,
        path="/",
        httponly=True,
        secure=secure,
        samesite=settings.auth_cookie_samesite,
    )


@router.post("/api/v1/auth/register", response_model=DataEnvelope[RegisterResponse])
def register(request: Request, response: Response, payload: RegisterRequest) -> DataEnvelope[RegisterResponse]:
    actor, tokens = register_with_email_password(
        email=payload.email,
        password=payload.password,
        full_name=payload.fullName,
        company_name=payload.companyName,
        wb_token=payload.wbToken,
        user_agent=request.headers.get("user-agent"),
        ip_address=_ip_from_request(request),
    )
    _set_refresh_cookie(response, tokens.refresh_token)
    me = build_cabinet_me(user_id=actor.user_id, current_session_id=actor.session_id)
    return DataEnvelope(
        data=RegisterResponse(
            organization=me.organization,
            user=me.user,
            accessToken=tokens.access_token,
            expiresIn=tokens.expires_in,
        )
    )


@router.post("/api/v1/auth/login", response_model=DataEnvelope[LoginResponse])
def login(request: Request, response: Response, payload: LoginRequest) -> DataEnvelope[LoginResponse]:
    tokens = login_with_email_password(
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=_ip_from_request(request),
    )
    _set_refresh_cookie(response, tokens.refresh_token)
    return DataEnvelope(
        data=LoginResponse(
            accessToken=tokens.access_token,
            expiresIn=tokens.expires_in,
        )
    )


@router.post("/api/v1/auth/refresh", response_model=DataEnvelope[RefreshResponse])
def refresh(request: Request, response: Response) -> DataEnvelope[RefreshResponse]:
    cookie_name = get_settings().auth_refresh_cookie_name
    refresh_token = request.cookies.get(cookie_name)
    tokens = refresh_access_token(
        refresh_token=refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=_ip_from_request(request),
    )
    _set_refresh_cookie(response, tokens.refresh_token)
    return DataEnvelope(
        data=RefreshResponse(
            accessToken=tokens.access_token,
            expiresIn=tokens.expires_in,
        )
    )


@router.post("/api/v1/auth/logout", response_model=DataEnvelope[dict[str, str]])
def logout(request: Request, response: Response) -> DataEnvelope[dict[str, str]]:
    actor = actor_from_request(request)
    logout_current_session(
        actor=actor,
        user_agent=request.headers.get("user-agent"),
        ip_address=_ip_from_request(request),
    )
    _clear_refresh_cookie(response)
    return DataEnvelope(data={"status": "ok"})
