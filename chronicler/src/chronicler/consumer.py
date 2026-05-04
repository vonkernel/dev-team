"""Valkey Streams Consumer 루프.

XREADGROUP → 이벤트 파싱 → 핸들러 호출 → XACK (성공 시).

wire `event_type` 문자열 → Python 이벤트 클래스 매핑은 EventHandler 의
`registered_event_types` 에서 동적 도출 (각 이벤트 클래스의 Literal default 값
이 wire 표기). 새 이벤트 type 추가 시 본 파일 수정 불필요 (OCP).
"""

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as redis
from pydantic import ValidationError

from dev_team_shared.event_bus.bus import A2A_EVENTS_STREAM
from dev_team_shared.event_bus.events import A2AEvent

from chronicler.handler import EventHandler

logger = logging.getLogger(__name__)


def _build_event_type_map(
    event_classes: tuple[type[A2AEvent], ...],
) -> dict[str, type[A2AEvent]]:
    """wire `event_type` (Literal default) → Python class.

    각 이벤트 클래스가 `event_type: Literal["..."] = "..."` 필드를 가짐.
    Pydantic 의 model_fields 에서 default 추출.
    """
    out: dict[str, type[A2AEvent]] = {}
    for cls in event_classes:
        field = cls.model_fields.get("event_type")
        if field is None:
            raise RuntimeError(
                f"event class {cls.__name__} missing `event_type` field",
            )
        wire = field.default
        if not isinstance(wire, str):
            raise RuntimeError(
                f"event class {cls.__name__} `event_type` default is not str: "
                f"{wire!r}",
            )
        out[wire] = cls
    return out


async def ensure_consumer_group(
    client: redis.Redis,
    *,
    stream: str = A2A_EVENTS_STREAM,
    group: str,
) -> None:
    """Consumer Group 이 없으면 생성. 이미 있으면 그대로."""
    try:
        await client.xgroup_create(stream, group, id="0", mkstream=True)
        logger.info("consumer group %r created on stream %r", group, stream)
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info("consumer group %r already exists", group)
        else:
            raise


async def run_consumer(
    client: redis.Redis,
    handler: EventHandler,
    *,
    group: str,
    consumer: str,
    batch_size: int = 10,
    block_ms: int = 5000,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Consumer 루프 — block_ms 단위로 stream poll. stop_event set 되면 종료.

    재시작 시 PEL 처리를 위해 처음에는 ID="0" (미처리 backlog), 그 후 ">" (새
    메시지) 로 전환.
    """
    event_type_map = _build_event_type_map(handler.registered_event_types)
    last_id_for_pel = "0"
    pel_drained = False

    while True:
        if stop_event and stop_event.is_set():
            logger.info("stop_event set — consumer exiting")
            return

        read_id = ">" if pel_drained else last_id_for_pel
        try:
            response = await client.xreadgroup(
                group,
                consumer,
                {A2A_EVENTS_STREAM: read_id},
                count=batch_size,
                block=block_ms,
            )
        except Exception:
            logger.exception("xreadgroup failed — sleeping 5s before retry")
            await asyncio.sleep(5)
            continue

        if not response:
            if not pel_drained:
                pel_drained = True
                logger.info("PEL drained — switching to new-message mode (>)")
            continue

        for _stream, messages in response:
            if not messages and not pel_drained:
                pel_drained = True
                continue
            for msg_id, fields in messages:
                await _process_one(
                    client, handler, event_type_map, msg_id, fields, group=group,
                )


async def _process_one(
    client: redis.Redis,
    handler: EventHandler,
    event_type_map: dict[str, type[A2AEvent]],
    msg_id: bytes,
    fields: dict[bytes, bytes],
    *,
    group: str,
) -> None:
    """메시지 1건 — parse → handle → XACK.

    parse 실패 (필드 누락 / unknown type / payload validation) 는 ack-and-skip
    (PEL 영구 적체 방지). handle 실패만 PEL 에 남겨 재시도.
    """
    # ── parse ────────────────────────────────────────────────────────
    try:
        event_type_raw = fields.get(b"event_type")
        payload_raw = fields.get(b"payload")
        if event_type_raw is None or payload_raw is None:
            logger.warning(
                "missing required field(s) msg_id=%s fields=%s — ack-and-skip",
                msg_id, list(fields.keys()),
            )
            await client.xack(A2A_EVENTS_STREAM, group, msg_id)
            return
        event_type = event_type_raw.decode("utf-8")
        payload = payload_raw.decode("utf-8")
        cls = event_type_map.get(event_type)
        if cls is None:
            logger.warning(
                "unknown event_type=%r msg_id=%s — ack-and-skip",
                event_type, msg_id,
            )
            await client.xack(A2A_EVENTS_STREAM, group, msg_id)
            return
        try:
            event: A2AEvent = cls.model_validate(json.loads(payload))
        except (ValidationError, json.JSONDecodeError):
            logger.exception(
                "invalid event payload msg_id=%s — ack-and-skip", msg_id,
            )
            await client.xack(A2A_EVENTS_STREAM, group, msg_id)
            return
    except Exception:
        logger.exception(
            "parse failed msg_id=%s — ack-and-skip (data 자체 오류)", msg_id,
        )
        try:
            await client.xack(A2A_EVENTS_STREAM, group, msg_id)
        except Exception:
            logger.exception("xack 도 실패 msg_id=%s", msg_id)
        return

    # ── handle ───────────────────────────────────────────────────────
    try:
        await handler.handle(event)
        await client.xack(A2A_EVENTS_STREAM, group, msg_id)
    except Exception:
        logger.exception(
            "handle failed msg_id=%s — leaving in PEL for retry", msg_id,
        )
        # 의도적으로 XACK 안 함 → PEL 에 남아 재시도


__all__ = ["ensure_consumer_group", "run_consumer"]
