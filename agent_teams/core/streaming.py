"""Streaming output utilities."""
from __future__ import annotations

from typing import AsyncIterator


async def collect_stream(stream: AsyncIterator[str]) -> str:
    """Collect all chunks from a stream into a single string."""
    parts: list[str] = []
    async for chunk in stream:
        parts.append(chunk)
    return "".join(parts)


async def tee_stream(stream: AsyncIterator[str], callback) -> str:
    """Stream content while calling a callback for each chunk. Returns full text."""
    parts: list[str] = []
    async for chunk in stream:
        parts.append(chunk)
        await callback(chunk)
    return "".join(parts)
