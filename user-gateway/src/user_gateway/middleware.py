"""HTTP 미들웨어.

응답 헤더 가공 등 횡단 관심사(cross-cutting) 를 라우트 로직과 분리 (SRP).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CacheControlMiddleware(BaseHTTPMiddleware):
    """정적 자원 Cache 정책 부여.

    - `/assets/<hash>.*` → `public, max-age=31536000, immutable`
      (Vite 가 파일명에 hash 붙이므로 안전)
    - `/` 또는 `*.html` → `no-cache` (HTML 안의 asset URL 이 hash 포함이라
      매번 fresh fetch 해도 실제 CDN 히트율엔 영향 없음)
    - 그 외 경로는 건드리지 않음 — API 응답은 각 핸들러가 결정.
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/assets/"):
            response.headers.setdefault(
                "Cache-Control", "public, max-age=31536000, immutable",
            )
        elif path == "/" or path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"
        return response


__all__ = ["CacheControlMiddleware"]
