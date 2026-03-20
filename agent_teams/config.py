"""Configuration loading and management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ProxyConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8317"
    api_key: str = "agent-teams-key-2026"
    timeout: int = 300


class RouteConfig(BaseModel):
    base_url: str = ""
    api_key: str = ""
    timeout: int = 300


class ExecutionConfig(BaseModel):
    backend: str = "api"
    default_route: str = "cliproxyapi"
    fallback_routes: list[str] = []
    parallel: bool = True
    max_parallel: int = 6


class AgentModelConfig(BaseModel):
    models: list[str] = []
    temperature: float = 0.5


class ImageGenConfig(BaseModel):
    model: str = "gemini-2.5-flash"
    fallback_models: list[str] = ["gemini-2.5-pro"]


class OutputConfig(BaseModel):
    default_dir: str = "./output"
    stream: bool = True


class Settings(BaseModel):
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    routes: dict[str, RouteConfig] = Field(default_factory=dict)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    agents: dict[str, AgentModelConfig] = Field(default_factory=dict)
    imagegen: ImageGenConfig = Field(default_factory=ImageGenConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)

    def route_names(self) -> list[str]:
        return list(self.routes.keys())

    def get_route_sequence(self) -> list[str]:
        names: list[str] = []
        primary = self.execution.default_route.strip()
        if primary:
            names.append(primary)
        for route in self.execution.fallback_routes:
            route = route.strip()
            if route and route not in names:
                names.append(route)
        if not names:
            names.append("cliproxyapi")
        return names

    def resolve_route(self, route_name: str) -> RouteConfig:
        if route_name in self.routes:
            return self.routes[route_name]
        if route_name == "subscription":
            return RouteConfig(
                base_url=self.proxy.base_url,
                api_key=self.proxy.api_key,
                timeout=self.proxy.timeout,
            )
        return RouteConfig()


_settings: Settings | None = None


def load_settings(config_path: str | Path | None = None) -> Settings:
    """Load settings from YAML file, with env var overrides."""
    global _settings
    if _settings is not None and config_path is None:
        return _settings

    if config_path is None:
        config_path = Path(__file__).parent / "settings.yaml"

    config_path = Path(config_path)
    data: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    data.setdefault("routes", {})
    if "subscription" not in data["routes"]:
        proxy = data.get("proxy", {})
        data["routes"]["subscription"] = {
            "base_url": proxy.get("base_url", ProxyConfig().base_url),
            "api_key": proxy.get("api_key", ProxyConfig().api_key),
            "timeout": proxy.get("timeout", ProxyConfig().timeout),
        }

    # Env var overrides
    if url := os.environ.get("AGENT_TEAMS_PROXY_URL"):
        data.setdefault("proxy", {})["base_url"] = url
    if key := os.environ.get("AGENT_TEAMS_API_KEY"):
        data.setdefault("proxy", {})["api_key"] = key
    if backend := os.environ.get("AGENT_TEAMS_BACKEND"):
        data.setdefault("execution", {})["backend"] = backend
    if default_route := os.environ.get("AGENT_TEAMS_ROUTE_DEFAULT"):
        data.setdefault("execution", {})["default_route"] = default_route
    if fallback_routes := os.environ.get("AGENT_TEAMS_FALLBACK_ROUTES"):
        data.setdefault("execution", {})["fallback_routes"] = [
            item.strip() for item in fallback_routes.split(",") if item.strip()
        ]
    if parallel := os.environ.get("AGENT_TEAMS_PARALLEL"):
        data.setdefault("execution", {})["parallel"] = parallel.strip().lower() not in {"0", "false", "no"}
    if max_parallel := os.environ.get("AGENT_TEAMS_MAX_PARALLEL"):
        data.setdefault("execution", {})["max_parallel"] = int(max_parallel)

    route_env_map = {
        "subscription": ("AGENT_TEAMS_SUBSCRIPTION_URL", "AGENT_TEAMS_SUBSCRIPTION_KEY"),
        "aicode": ("AGENT_TEAMS_AICODE_URL", "AGENT_TEAMS_AICODE_KEY"),
        "cliproxyapi": ("AGENT_TEAMS_CLIPROXYAPI_URL", "AGENT_TEAMS_CLIPROXYAPI_KEY"),
    }
    for route_name, (url_key, api_key_key) in route_env_map.items():
        route = data.setdefault("routes", {}).setdefault(route_name, {})
        if url := os.environ.get(url_key):
            route["base_url"] = url
        if key := os.environ.get(api_key_key):
            route["api_key"] = key

    # Keep proxy overrides aligned with the unified cliproxyapi route.
    proxy = data.setdefault("proxy", {})
    cliproxyapi = data.setdefault("routes", {}).setdefault("cliproxyapi", {})
    if proxy.get("base_url") and not cliproxyapi.get("base_url"):
        cliproxyapi["base_url"] = proxy["base_url"]
    if proxy.get("api_key") and not cliproxyapi.get("api_key"):
        cliproxyapi["api_key"] = proxy["api_key"]
    if proxy.get("timeout") and not cliproxyapi.get("timeout"):
        cliproxyapi["timeout"] = proxy["timeout"]

    # Keep subscription aligned with proxy overrides for backward compatibility.
    subscription = data.setdefault("routes", {}).setdefault("subscription", {})
    if proxy.get("base_url"):
        subscription["base_url"] = proxy["base_url"]
    if proxy.get("api_key"):
        subscription["api_key"] = proxy["api_key"]
    if proxy.get("timeout"):
        subscription["timeout"] = proxy["timeout"]

    _settings = Settings(**data)
    return _settings


def get_settings() -> Settings:
    return load_settings()
