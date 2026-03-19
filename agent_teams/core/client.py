"""Async HTTP client with route fallback for OpenAI-compatible gateways."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any, AsyncIterator

import httpx

from agent_teams.config import get_settings

# Ensure local connections bypass system proxy (e.g. Clash)
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
if "127.0.0.1" not in os.environ.get("NO_PROXY", ""):
    os.environ["NO_PROXY"] = os.environ.get("NO_PROXY", "") + ",127.0.0.1,localhost"


class LLMClient:
    """OpenAI-compatible async client with automatic route fallback."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, timeout: int | None = None):
        settings = get_settings()
        self.base_url = (base_url or settings.proxy.base_url).rstrip("/")
        self.api_key = api_key or settings.proxy.api_key
        self.timeout = timeout or settings.proxy.timeout
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._available_models: list[str] | None = None

    def _route_candidates(self) -> list[tuple[str, str, str, int]]:
        settings = get_settings()
        candidates: list[tuple[str, str, str, int]] = []
        for route_name in settings.get_route_sequence():
            route = settings.resolve_route(route_name)
            if route.base_url and route.api_key:
                candidates.append((route_name, route.base_url.rstrip("/"), route.api_key, route.timeout or self.timeout))
        if not candidates:
            candidates.append(("subscription", self.base_url, self.api_key, self.timeout))
        return candidates

    async def _get_client(self, route_name: str, base_url: str, api_key: str, timeout: int) -> httpx.AsyncClient:
        client = self._clients.get(route_name)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(timeout, connect=10),
            )
            self._clients[route_name] = client
        return client

    @staticmethod
    def _should_retry(exc: Exception) -> bool:
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in (429, 500, 502, 503, 504)
        return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError))

    async def close(self) -> None:
        for client in self._clients.values():
            if not client.is_closed:
                await client.aclose()
        self._clients.clear()

    async def list_models(self) -> list[str]:
        """Fetch available models from the first healthy route."""
        if self._available_models is not None:
            return self._available_models
        for route_name, base_url, api_key, timeout in self._route_candidates():
            client = await self._get_client(route_name, base_url, api_key, timeout)
            try:
                resp = await client.get("/v1/models")
                resp.raise_for_status()
                data = resp.json()
                self._available_models = [m["id"] for m in data.get("data", [])]
                return self._available_models
            except Exception:
                continue
        self._available_models = []
        return self._available_models

    async def pick_model(self, preferences: list[str]) -> str:
        """Pick the first available model from preference list."""
        available = await self.list_models()
        if not available:
            # If we can't query models, just use the first preference
            return preferences[0] if preferences else "claude-sonnet-4-20250514"
        for model in preferences:
            # Exact match or prefix match
            for avail in available:
                if model == avail or avail.startswith(model):
                    return avail
        # Fallback: return first preference anyway (let CLIProxyAPI handle routing)
        return preferences[0] if preferences else available[0]

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.5,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Non-streaming chat completion with route fallback."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        last_error: Exception | None = None
        for route_name, base_url, api_key, timeout in self._route_candidates():
            client = await self._get_client(route_name, base_url, api_key, timeout)
            for attempt in range(4):
                try:
                    resp = await client.post("/v1/chat/completions", json=payload)
                    if resp.status_code == 429:
                        wait = min(2 ** attempt * 5, 60)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    data["_route"] = route_name
                    return data
                except Exception as exc:
                    last_error = exc
                    if self._should_retry(exc) and attempt < 3:
                        await asyncio.sleep(min(2 ** attempt * 5, 60))
                        continue
                    break
        if last_error:
            raise last_error
        return {}

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float = 0.5,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streaming chat completion, yields content deltas."""
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        last_error: Exception | None = None
        for route_name, base_url, api_key, timeout in self._route_candidates():
            client = await self._get_client(route_name, base_url, api_key, timeout)
            for attempt in range(4):
                try:
                    async with client.stream("POST", "/v1/chat/completions", json=payload) as resp:
                        if resp.status_code == 429:
                            await resp.aread()
                            await asyncio.sleep(min(2 ** attempt * 5, 60))
                            continue
                        resp.raise_for_status()
                        async for line in resp.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                if content := delta.get("content"):
                                    yield content
                            except (json.JSONDecodeError, IndexError, KeyError):
                                continue
                        return
                except Exception as exc:
                    last_error = exc
                    if self._should_retry(exc) and attempt < 3:
                        await asyncio.sleep(min(2 ** attempt * 5, 60))
                        continue
                    break
        if last_error:
            raise last_error

    async def generate_image_via_gemini(
        self,
        prompt: str,
        model: str = "gemini-2.5-flash",
    ) -> dict[str, Any]:
        """Generate image using Nano Banana (Gemini image generation) via CLIProxyAPI.

        Uses the Gemini model's native image generation capability.
        The response may contain inline image data.
        """
        messages = [{"role": "user", "content": prompt}]
        return await self.chat(messages=messages, model=model, temperature=0.8)


# Singleton
_client: LLMClient | None = None


def get_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
