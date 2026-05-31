from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import get_settings
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    OAuthCallbackRequest,
    OAuthLoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.utils.auth import CurrentUser, create_access_token
from app.utils.logging import get_logger
from app.utils.metrics import get_metrics
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/api/v1/auth")
logger = get_logger("auth")
settings = get_settings()
metrics = get_metrics()

_engine: Any = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def _get_session() -> AsyncSession:
    global _engine, _session_factory
    if _engine is None:
        _engine = create_async_engine(settings.resolved_database_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    assert _session_factory is not None
    return _session_factory()


def _hash_password(password: str) -> str:
    import hashlib
    import os

    salt = os.urandom(16).hex()
    pwd_hash = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{pwd_hash}"


def _verify_password(password: str, stored: str) -> bool:
    import hashlib

    parts = stored.split(":")
    if len(parts) != 2:
        return False
    salt, expected = parts
    return hashlib.sha256((salt + password).encode()).hexdigest() == expected


OAUTH_PROVIDERS: dict[str, dict[str, str]] = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "scope": "openid email profile",
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "client_id": settings.github_client_id,
        "client_secret": settings.github_client_secret,
        "scope": "read:user user:email",
    },
}


@router.post("/register", response_model=UserResponse)
@limiter.exempt  # type: ignore[misc]
async def register(request: Request, body: RegisterRequest) -> UserResponse:
    if not body.email or not body.password:
        raise HTTPException(status_code=422, detail="Email and password are required")

    password_hash = _hash_password(body.password)
    user_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    from app.config.settings import get_settings as _get_settings

    _settings = _get_settings()
    admin_emails = {e.strip().lower() for e in _settings.admin_emails.split(",") if e.strip()}
    role = "admin" if body.email.lower() in admin_emails else "user"

    async with await _get_session() as session:
        existing = await session.execute(
            text("SELECT id FROM users WHERE email = :email"), {"email": body.email}
        )
        if existing.fetchone():
            raise HTTPException(status_code=409, detail="Email already registered")

        await session.execute(
            text("""
                INSERT INTO users (id, email, password_hash, name, role, created_at, updated_at)
                VALUES (:id, :email, :password_hash, :name, :role, :created_at, :updated_at)
            """),
            {
                "id": user_id,
                "email": body.email,
                "password_hash": password_hash,
                "name": body.name,
                "role": role,
                "created_at": now,
                "updated_at": now,
            },
        )
        await session.commit()

    metrics.inc("auth.register.success")
    logger.log_action("auth", "register", f"User {body.email} created")

    return UserResponse(
        id=user_id,
        email=body.email,
        name=body.name,
        role="user",
    )


@router.post("/login", response_model=LoginResponse)
@limiter.exempt  # type: ignore[misc]
async def login(request: Request, body: LoginRequest) -> LoginResponse:
    if not body.email or not body.password:
        raise HTTPException(status_code=422, detail="Email and password are required")

    async with await _get_session() as session:
        row = await session.execute(
            text(
                "SELECT id, email, password_hash, name, avatar_url, role"
                " FROM users WHERE email = :email"
            ),
            {"email": body.email},
        )
        user = row.fetchone()

    if (
        not user
        or not user.password_hash
        or not _verify_password(body.password, user.password_hash)
    ):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    from app.config.settings import get_settings as _get_settings

    _settings = _get_settings()
    admin_emails = {e.strip().lower() for e in _settings.admin_emails.split(",") if e.strip()}
    effective_role = "admin" if body.email.lower() in admin_emails else (user.role or "user")

    access_token = create_access_token(
        sub=str(user.id),
        workspace="default",
        role=effective_role,
    )

    metrics.inc("auth.login.success")
    logger.log_action("auth", "login", f"User {user.email} logged in")

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            role=effective_role,
        ),
    )


@router.get("/{provider}/login", response_model=OAuthLoginRequest)
async def oauth_login(
    provider: str, redirect_uri: str = "agentos://oauth/callback"
) -> OAuthLoginRequest:
    config = OAUTH_PROVIDERS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    params = {
        "client_id": config["client_id"],
        "redirect_uri": redirect_uri,
        "scope": config["scope"],
        "response_type": "code",
        "access_type": "offline",
    }
    auth_url = f"{config['authorize_url']}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    metrics.inc(f"auth.oauth.{provider}.initiated")
    logger.log_action("auth", "oauth_login", f"OAuth {provider} login initiated")

    return OAuthLoginRequest(authorization_url=auth_url)


@router.post("/{provider}/callback", response_model=LoginResponse)
async def oauth_callback(
    provider: str,
    body: OAuthCallbackRequest,
    redirect_uri: str = "agentos://oauth/callback",
) -> LoginResponse:
    config = OAUTH_PROVIDERS.get(provider)
    if not config:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            config["token_url"],
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "code": body.code,
                "redirect_uri": body.redirect_uri or redirect_uri,
                "grant_type": "authorization_code",
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange authorization code")

        token_data = token_resp.json()
        access_token_resp = token_data.get("access_token")

        userinfo_resp = await client.get(
            config["userinfo_url"],
            headers={"Authorization": f"Bearer {access_token_resp}"},
        )
        if userinfo_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch user info")

        userinfo = userinfo_resp.json()

    provider_user_id = str(userinfo.get("id", userinfo.get("sub", "")))
    provider_email = userinfo.get("email", "")
    provider_name = userinfo.get("name", "")
    provider_avatar = userinfo.get("picture", userinfo.get("avatar_url", ""))

    async with await _get_session() as session:
        existing_social = await session.execute(
            text("""
                SELECT u.id, u.email, u.name, u.avatar_url, u.role
                FROM social_accounts sa
                JOIN users u ON u.id = sa.user_id
                WHERE sa.provider = :provider AND sa.provider_user_id = :provider_user_id
            """),
            {"provider": provider, "provider_user_id": provider_user_id},
        )
        social_row = existing_social.fetchone()

        if social_row:
            access_token = create_access_token(
                sub=str(social_row.id),
                workspace="default",
                role=social_row.role or "user",
            )
            metrics.inc(f"auth.oauth.{provider}.linked")
            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                user=UserResponse(
                    id=str(social_row.id),
                    email=social_row.email,
                    name=social_row.name,
                    avatar_url=social_row.avatar_url,
                    role=social_row.role or "user",
                ),
            )

        existing_user = await session.execute(
            text("SELECT id, email, name, avatar_url, role FROM users WHERE email = :email"),
            {"email": provider_email},
        )
        existing_row = existing_user.fetchone()

        user_id: str
        if existing_row:
            user_id = str(existing_row.id)
        else:
            user_id = str(uuid.uuid4())
            now = datetime.now(UTC)
            await session.execute(
                text("""
                    INSERT INTO users (id, email, name, avatar_url, created_at, updated_at)
                    VALUES (:id, :email, :name, :avatar_url, :created_at, :updated_at)
                """),
                {
                    "id": user_id,
                    "email": provider_email,
                    "name": provider_name,
                    "avatar_url": provider_avatar,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        await session.execute(
            text("""
                INSERT INTO social_accounts
                    (user_id, provider, provider_user_id, provider_email, access_token)
                VALUES (:user_id, :provider, :provider_user_id, :provider_email, :access_token)
            """),
            {
                "user_id": user_id,
                "provider": provider,
                "provider_user_id": provider_user_id,
                "provider_email": provider_email,
                "access_token": access_token_resp,
            },
        )
        await session.commit()

    access_token = create_access_token(
        sub=user_id,
        workspace="default",
        role="user",
    )
    metrics.inc(f"auth.oauth.{provider}.registered")
    logger.log_action(
        "auth", "oauth_callback", f"OAuth {provider} user {provider_email} registered"
    )

    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user_id,
            email=provider_email,
            name=provider_name,
            avatar_url=provider_avatar,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    async with await _get_session() as session:
        row = await session.execute(
            text("SELECT id, email, name, avatar_url, role FROM users WHERE id = :id"),
            {"id": user.sub},
        )
        user_row = row.fetchone()

    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        id=str(user_row.id),
        email=user_row.email,
        name=user_row.name,
        avatar_url=user_row.avatar_url,
        role=user_row.role or "user",
    )
