"""
Интеграция с панелью 3x-ui — выдача и отзыв реальных VLESS+Reality ключей.

Документация API: https://github.com/MHSanaei/3x-ui (панель отдаёт REST API
под cookie-сессией админа — отдельного API-ключа у панели нет).

Поток выдачи ключа:
1. POST {panel}/login — логин, получаем cookie-сессию.
2. POST {panel}/panel/api/inbounds/addClient — добавляем клиента в inbound.
3. Собираем vless:// ссылку из Reality-параметров, заданных в .env
   (они стабильны — снимаются один раз в UI панели при создании inbound,
   не вытаскиваются из ответа API, чтобы не зависеть от версии панели).

ponytail: один физический сервер/панель на инсталляцию (XUI_* — плоские
переменные, не список). Для нескольких серверов — замени на JSON-карту
{country: config} и выбирай по VPNKey.country; для MVP с одним сервером
это лишняя сложность.
"""
import logging
import re
from uuid import uuid4

import aiohttp

from config import settings

logger = logging.getLogger("blacklotus.xui")

_UUID_RE = re.compile(r"vless://([0-9a-fA-F-]{36})@")


class XuiError(RuntimeError):
    """Панель недоступна или вернула ошибку."""


async def _login(http: aiohttp.ClientSession) -> None:
    url = f"{settings.XUI_PANEL_URL.rstrip('/')}/login"
    async with http.post(
        url,
        json={"username": settings.XUI_USERNAME, "password": settings.XUI_PASSWORD},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as resp:
        if resp.status != 200:
            raise XuiError(f"панель вернула {resp.status} на /login")
        body = await resp.json(content_type=None)
        if not body.get("success", False):
            raise XuiError(f"логин в панель отклонён: {body.get('msg', body)}")


async def create_client(email_label: str) -> str:
    """
    Завести нового клиента в настроенном inbound и вернуть готовую
    vless:// ссылку (VLESS + Reality).

    email_label — произвольная метка клиента в панели (видно в UI 3x-ui),
    обычно "tg<id>-<country>" — удобно искать/удалять вручную.
    """
    if not settings.has_real_vpn_panel:
        raise XuiError("панель не настроена (XUI_* пусты)")

    client_uuid = str(uuid4())
    client = {
        "id": client_uuid,
        "flow": settings.XUI_FLOW,
        "email": email_label,
        "limitIp": 0,
        "totalGB": 0,
        "expiryTime": 0,
        "enable": True,
        "tgId": "",
        "subId": uuid4().hex[:16],
    }
    import json as _json
    payload = {
        "id": settings.XUI_INBOUND_ID,
        "settings": _json.dumps({"clients": [client]}),
    }

    async with aiohttp.ClientSession() as http:
        await _login(http)
        url = f"{settings.XUI_PANEL_URL.rstrip('/')}/panel/api/inbounds/addClient"
        try:
            async with http.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                body = await resp.json(content_type=None)
        except aiohttp.ClientError as e:
            raise XuiError(f"сеть до панели: {e}") from e
        if not body.get("success", False):
            raise XuiError(f"панель отклонила клиента: {body.get('msg', body)}")

    logger.info("xui: клиент создан, email=%s", email_label)
    return _build_vless_uri(client_uuid, email_label)


async def delete_client(key_value: str) -> bool:
    """
    Удалить клиента с панели по UUID, который зашит в его же vless-ссылке.
    Используется при отзыве подписки. Best-effort: сетевая ошибка не кидает
    исключение наружу — отзыв в БД важнее, чем синхронный ответ панели.
    """
    if not settings.has_real_vpn_panel:
        return False
    m = _UUID_RE.search(key_value)
    if not m:
        return False
    client_uuid = m.group(1)

    try:
        async with aiohttp.ClientSession() as http:
            await _login(http)
            url = (
                f"{settings.XUI_PANEL_URL.rstrip('/')}/panel/api/inbounds/"
                f"{settings.XUI_INBOUND_ID}/delClient/{client_uuid}"
            )
            async with http.post(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                body = await resp.json(content_type=None)
                return bool(body.get("success", False))
    except Exception as e:
        logger.warning("xui: не удалось удалить клиента %s: %s", client_uuid, e)
        return False


def _build_vless_uri(client_uuid: str, remark: str) -> str:
    """VLESS+Reality share-ссылка из стабильных параметров инбаунда (.env)."""
    host = settings.XUI_SERVER_HOST
    port = settings.XUI_SERVER_PORT
    pbk = settings.XUI_REALITY_PUBLIC_KEY
    sid = settings.XUI_REALITY_SHORT_ID
    sni = settings.XUI_REALITY_SNI
    flow = settings.XUI_FLOW
    return (
        f"vless://{client_uuid}@{host}:{port}"
        f"?type=tcp&security=reality&pbk={pbk}&fp=chrome&sni={sni}"
        f"&sid={sid}&spx=%2F&flow={flow}#{remark}"
    )
