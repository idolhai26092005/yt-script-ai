import asyncio
import json
import logging
from contextlib import suppress


logger = logging.getLogger("uvicorn.error")

SSE_HEARTBEAT_INTERVAL_SEC = 15.0


# SSE framing guard: frontend stream parsing depends on exact "data:" framing,
# so producers/endpoints share this helper instead of hand-building chunks.
def sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


# SSE resilience guard: long production streams must stay alive and surface
# generator crashes as structured events without changing public payload keys.
async def safe_sse_stream(source, heartbeat_interval: float = SSE_HEARTBEAT_INTERVAL_SEC):
    """Keep SSE alive and convert generator crashes into structured stream errors."""
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=8)

    async def pump_source() -> None:
        try:
            async for chunk in source:
                await queue.put(chunk)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Production SSE stream crashed.")
            await queue.put(sse_event({
                "status": "error",
                "message": f"Luồng sinh kịch bản bị ngắt: {str(exc)}",
            }))
        finally:
            await queue.put(None)

    pump_task = asyncio.create_task(pump_source())
    try:
        while True:
            try:
                chunk = await asyncio.wait_for(queue.get(), timeout=heartbeat_interval)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue

            if chunk is None:
                break
            yield chunk
    finally:
        if not pump_task.done():
            pump_task.cancel()
            with suppress(asyncio.CancelledError):
                await pump_task
