import asyncio
import json

import pytest

from app.api.v1.endpoints.script_production import safe_sse_stream


async def collect_stream(source):
    return [chunk async for chunk in source]


@pytest.mark.asyncio
async def test_safe_sse_stream_converts_generator_crash_to_error_event():
    async def broken_source():
        yield 'data: {"status": "generating", "step": "phase0"}\n\n'
        raise RuntimeError("phase gate failed")

    chunks = await collect_stream(safe_sse_stream(broken_source(), heartbeat_interval=0.01))

    assert chunks[0].startswith("data: ")
    error_chunk = next(chunk for chunk in chunks if '"status": "error"' in chunk)
    payload = json.loads(error_chunk.removeprefix("data: ").strip())
    assert payload["status"] == "error"
    assert "phase gate failed" in payload["message"]


@pytest.mark.asyncio
async def test_safe_sse_stream_emits_heartbeat_while_source_is_idle():
    async def slow_source():
        await asyncio.sleep(0.03)
        yield 'data: {"status": "done"}\n\n'

    chunks = await collect_stream(safe_sse_stream(slow_source(), heartbeat_interval=0.01))

    assert ": ping\n\n" in chunks
    assert chunks[-1] == 'data: {"status": "done"}\n\n'
