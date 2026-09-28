"""
FastAPI-приложение — статика мини-приложения + JSON API.

Безопасность:
- обязательная проверка Telegram initData (HMAC-SHA256);
- rate limit через slowapi;
- CORS только с ALLOWED_ORIGIN;
- заголовки HSTS/CSP/X-Frame-Options и т.д.

Dev-режим (DEBUG=true) разрешает работу без initData от имени ADMIN_ID —
в проде обязательно DEBUG=false.
"""
import logging
from pathlib import Path

import aiohttp
from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.database import get_session, init_db
from db.repo import (
    PLANS,
    SERVERS,
    add_support_message,
    generate_key,
    get_or_create_user,
    grant_subscription,
    list_keys,
)
from security.logging_setup import audit, setup_logging
from webapp.middleware import SecurityHeadersMiddleware
from webapp.tg_auth import verify_init_data


setup_logging()
logger = logging.getLogger("blacklotus.webapp")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="BlackLotusVPN WebApp", docs_url=None, redoc_url=None,
              openapi_url=None)

# ── Rate limiting: N req/min на IP ──────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security headers ────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)

# ── CORS: только домен мини-приложения ──────────────────────────────
allowed = settings.ALLOWED_ORIGIN or settings.WEBAPP_URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=[allowed] if allowed else [],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Init-Data"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
async def _startup() -> None:
    await init_db()
    logger.info("WebApp запущен, prod=%s", settings.is_prod)


# ── Аутентификация ─────────────────────────────────────────────────

async def current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
    x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
):
    """
    Извлекает пользователя из подписанного initData Telegram WebApp.
    В prod без валидного initData — 401.
    В DEBUG — fallback на ADMIN_ID для локальной отладки в браузере.
    """
    parsed = verify_init_data(x_init_data) if x_init_data else None
    if parsed and parsed.get("user"):
        tg_user = parsed["user"]
        return await get_or_create_user(
            session,
            tg_id=int(tg_user["id"]),
            username=tg_user.get("username"),
            full_name=" ".join(
                filter(None, [tg_user.get("first_name"), tg_user.get("last_name")])
            ) or None,
        )

    if settings.is_prod:
        # В проде — жёстко 401, без утечки причины
        raise HTTPException(status_code=401, detail="unauthorized")

    logger.warning("DEBUG: initData отсутствует — используем ADMIN_ID")
    return await get_or_create_user(
        session, tg_id=settings.ADMIN_ID, username="admin", full_name="Admin"
    )


# ── Глобальный обработчик 500 с алертом админу ─────────────────────

@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    logger.exception("API 500: %s %s -> %s", request.method, request.url.path, exc)
    # Best-effort уведомление админу через Bot API (без исключений)
    try:
        text = (
            f"🚨 <b>API error 500</b>\n"
            f"{request.method} {request.url.path}\n"
            f"<code>{type(exc).__name__}: {exc}</code>"
        )
        api_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as http:
            await http.post(api_url, json={
                "chat_id": settings.ADMIN_ID,
                "text": text,
                "parse_mode": "HTML",
            }, timeout=aiohttp.ClientTimeout(total=5))
    except Exception:
        pass
    return JSONResponse({"error": "internal"}, status_code=500)


# ── Индексная страница ────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
@limiter.limit("60/minute")
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


# ── API ────────────────────────────────────────────────────────────

@app.get("/api/me")
@limiter.limit("60/minute")
async def api_me(request: Request, user=Depends(current_user)) -> dict:
    sub = user.subscription
    return {
        "tg_id": user.tg_id,
        "username": user.username,
        "full_name": user.full_name,
        "is_subscribed": bool(user.is_subscribed and sub),
        "subscription": (
            {
                "plan": sub.plan,
                "started_at": sub.started_at.isoformat(),
                "expires_at": sub.expires_at.isoformat(),
            }
            if sub
            else None
        ),
    }


@app.get("/api/plans")
@limiter.limit("60/minute")
async def api_plans(request: Request) -> dict:
    return {"plans": PLANS, "servers": SERVERS}


class PayRequest(BaseModel):
    plan: str = Field(..., pattern=r"^(1m|3m|12m)$")


@app.post("/api/pay")
@limiter.limit("10/minute")
async def api_pay(
    request: Request,
    payload: PayRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    if payload.plan not in PLANS:
        raise HTTPException(400, detail="unknown plan")
    sub = await grant_subscription(session, user, payload.plan)
    audit(user.tg_id, "self_pay_stub", plan=payload.plan)
    return {"ok": True, "plan": sub.plan, "expires_at": sub.expires_at.isoformat()}


class KeyRequest(BaseModel):
    country: str = Field(default="nl", min_length=2, max_length=8,
                         pattern=r"^[a-z]{2,8}$")


@app.post("/api/keys")
@limiter.limit("10/minute")
async def api_generate_key(
    request: Request,
    payload: KeyRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    if not any(s["code"] == payload.country for s in SERVERS):
        raise HTTPException(400, detail="unknown server")
    key = await generate_key(session, user, payload.country)
    audit(user.tg_id, "key_generated", country=payload.country, key_id=key.id)
    # На выход отдаём расшифрованное значение (только этому юзеру)
    from security.crypto import try_decrypt
    return {
        "id": key.id,
        "country": key.country,
        "key_value": try_decrypt(key.key_value),
        "created_at": key.created_at.isoformat(),
    }


@app.get("/api/keys")
@limiter.limit("30/minute")
async def api_list_keys(
    request: Request,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    keys = await list_keys(session, user)
    return {
        "keys": [
            {
                "id": k.id,
                "country": k.country,
                "key_value": k.key_value,  # уже расшифровано в repo
                "created_at": k.created_at.isoformat(),
            }
            for k in keys
        ]
    }


class SupportRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


@app.post("/api/support")
@limiter.limit("5/minute")
async def api_support(
    request: Request,
    payload: SupportRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    text = payload.text.strip()
    if not text:
        raise HTTPException(400, detail="empty message")

    await add_support_message(session, user, text)
    audit(user.tg_id, "support_message", length=len(text))

    tg_text = (
        f"🆘 <b>Обращение в поддержку</b>\n"
        f"От: <code>{user.tg_id}</code> (@{user.username or '—'})\n\n{text}"
    )
    api_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as http:
            await http.post(api_url, json={
                "chat_id": settings.ADMIN_ID,
                "text": tg_text,
                "parse_mode": "HTML",
            }, timeout=aiohttp.ClientTimeout(total=10))
    except Exception as e:
        logger.exception("Не смогли отправить сообщение админу: %s", e)

    return {"ok": True}
