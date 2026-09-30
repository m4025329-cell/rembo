"""
Middleware мини-приложения: заголовки безопасности + доверенные origin'ы.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


# CSP: telegram.org (SDK), cdnjs (qrcode-generator), Google Fonts, self.
# Inline-скрипт мини-приложения разрешён только по nonce (генерируется на запрос в index()).
def _csp(nonce: str | None) -> str:
    script_src = "'self' https://telegram.org https://cdnjs.cloudflare.com"
    if nonce:
        script_src += f" 'nonce-{nonce}'"
    return (
        "default-src 'self'; "
        f"script-src {script_src}; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors https://web.telegram.org https://*.telegram.org; "
        "base-uri 'self'; "
        "object-src 'none';"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Ставит стандартный набор защитных заголовков на каждый ответ.
    Учитывает, что мини-приложение открывается внутри Telegram-iframe.
    """

    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        headers = response.headers
        headers.setdefault(
            "Strict-Transport-Security",
            "max-age=63072000; includeSubDomains; preload",
        )
        # WebApp Telegram кладёт нас в iframe только со своего домена
        headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=()",
        )
        headers.setdefault(
            "Content-Security-Policy", _csp(getattr(request.state, "csp_nonce", None))
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
        return response
