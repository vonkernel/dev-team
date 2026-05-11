"""헬스체크 + Primary AgentCard 프록시."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from user_gateway.upstream import A2AUpstream

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@router.get("/api/agent-card")
async def get_agent_card(request: Request) -> JSONResponse:
    """Primary 의 AgentCard 를 프록시 (브라우저 CORS 회피)."""
    upstream: A2AUpstream = request.app.state.upstream
    try:
        card = await upstream.fetch_agent_card()
    except httpx.HTTPError as exc:
        logger.exception("failed to fetch primary AgentCard")
        raise HTTPException(
            status_code=502,
            detail=f"upstream agent-card fetch failed: {exc}",
        ) from exc
    return JSONResponse(card)


__all__ = ["router"]
