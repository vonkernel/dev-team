"""Chronicler 진입점 — 단일 스크립트.

Valkey 연결 + Document DB MCP 클라이언트 생성 + consumer 루프 기동.
SIGTERM / SIGINT 시 graceful shutdown (PEL 보존).
"""

from __future__ import annotations

import asyncio
import logging
import signal

import redis.asyncio as redis
from dev_team_shared.mcp_client import StreamableMCPClient

from chronicler.config import Settings
from chronicler.consumer import ensure_consumer_group, run_consumer
from chronicler.handler import EventHandler
from chronicler.processors import ALL_PROCESSORS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def _amain() -> None:
    settings = Settings()
    logger.info(
        "chronicler starting — valkey=%s mcp=%s group=%s consumer=%s",
        settings.valkey_url,
        settings.document_db_mcp_url,
        settings.consumer_group,
        settings.consumer_name,
    )

    # Valkey 클라이언트
    valkey = redis.from_url(settings.valkey_url, decode_responses=False)
    try:
        await valkey.ping()
    except Exception:
        logger.exception("valkey ping failed at startup")
        raise

    # Consumer Group 보장
    await ensure_consumer_group(valkey, group=settings.consumer_group)

    # Document DB MCP 클라이언트 + EventHandler (processors 주입)
    mcp = await StreamableMCPClient.connect(settings.document_db_mcp_url)
    handler = EventHandler(ALL_PROCESSORS, mcp)

    # graceful shutdown
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            # Windows / 일부 환경 — graceful 안 됨, KeyboardInterrupt 로 처리됨
            pass

    try:
        await run_consumer(
            valkey,
            handler,
            group=settings.consumer_group,
            consumer=settings.consumer_name,
            batch_size=settings.batch_size,
            block_ms=settings.block_ms,
            stop_event=stop,
        )
    finally:
        logger.info("chronicler shutting down")
        await mcp.aclose()
        await valkey.aclose()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()


__all__ = ["main"]
