"""
FastAPI-приложение — статика мини-приложения + JSON API для него.

Запуск локально:
    uvicorn webapp.main:app --host 0.0.0.0 --port 8080 --reload
"""
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import aiohttp

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
from webapp.tg_auth import verify_init_data


logger = logging.getLogger("blacklotus.webapp")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

app = FastAPI(title="BlackLotusVPN WebApp")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
async def _startup() -> None:
    """Подготовить БД."""
    await init_db()


# ------------- Аутентификация -------------

async def current_user(
    session: AsyncSession = Depends(get_session),
    x_init_data: str | None = Header(default=None, alias="X-Init-Data"),
):
    """
    Достаёт Telegram-пользователя из заголовка X-Init-Data.
    В dev-режиме допускаем пустой initData и работаем от имени ADMIN_ID
    (удобно открывать мини-приложение в браузере).
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
    # Fallback для локальной отладки: работаем от админа
    logger.warning("initData отсутствует/невалиден — используем ADMIN_ID для отладки")
    return await get_or_create_user(session, tg_id=settings.ADMIN_ID,
                                    username="admin", full_name="Admin")


# ------------- Страница мини-приложения -------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    """Отдаёт HTML мини-приложения."""
    return templates.TemplateResponse("index.html", {"request": request})


# ------------- API -------------

@app.get("/api/me")
async def api_me(user=Depends(current_user)) -> dict:
    """Инфо о пользователе + подписка."""
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
async def api_plans() -> dict:
    """Список тарифов и серверов."""
    return {"plans": PLANS, "servers": SERVERS}


class PayRequest(BaseModel):
    plan: str


@app.post("/api/pay")
async def api_pay(
    payload: PayRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    """
    Заглушка оплаты: моментально активируем подписку.
    Позже сюда встроим ЮKassa / Crypto / Stars.
    """
    if payload.plan not in PLANS:
        raise HTTPException(400, detail="Неизвестный тариф")
    sub = await grant_subscription(session, user, payload.plan)
    return {
        "ok": True,
        "plan": sub.plan,
        "expires_at": sub.expires_at.isoformat(),
    }


class KeyRequest(BaseModel):
    country: str = "nl"


@app.post("/api/keys")
async def api_generate_key(
    payload: KeyRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    """Сгенерировать VPN-ключ (заглушка UUID)."""
    if not any(s["code"] == payload.country for s in SERVERS):
        raise HTTPException(400, detail="Неизвестный сервер")
    key = await generate_key(session, user, payload.country)
    return {
        "id": key.id,
        "country": key.country,
        "key_value": key.key_value,
        "created_at": key.created_at.isoformat(),
    }


@app.get("/api/keys")
async def api_list_keys(
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    keys = await list_keys(session, user)
    return {
        "keys": [
            {
                "id": k.id,
                "country": k.country,
                "key_value": k.key_value,
                "created_at": k.created_at.isoformat(),
            }
            for k in keys
        ]
    }


class SupportRequest(BaseModel):
    text: str


@app.post("/api/support")
async def api_support(
    payload: SupportRequest,
    session: AsyncSession = Depends(get_session),
    user=Depends(current_user),
) -> dict:
    """
    Принять сообщение из формы поддержки:
    - сохраняет в БД
    - шлёт админу в Telegram напрямую через Bot API.
    """
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(400, detail="Пустое сообщение")
    if len(text) > 4000:
        raise HTTPException(400, detail="Сообщение слишком длинное")

    await add_support_message(session, user, text)

    tg_text = (
        f"🆘 <b>Обращение в поддержку</b>\n"
        f"От: <code>{user.tg_id}</code> "
        f"(@{user.username or '—'})\n\n{text}"
    )
    api_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/sendMessage"
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                api_url,
                json={
                    "chat_id": settings.ADMIN_ID,
                    "text": tg_text,
                    "parse_mode": "HTML",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.error("sendMessage failed: %s", await resp.text())
    except Exception as e:
        logger.exception("Не смогли отправить сообщение админу: %s", e)

    return {"ok": True}
