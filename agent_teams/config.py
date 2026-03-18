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
    agents: dict[str, AgentModelConfig] = Field(default_factory=dict)
    imagegen: ImageGenConfig = Field(default_factory=ImageGenConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


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

    # Env var overrides
    if url := os.environ.get("AGENT_TEAMS_PROXY_URL"):
        data.setdefault("proxy", {})["base_url"] = url
    if key := os.environ.get("AGENT_TEAMS_API_KEY"):
        data.setdefault("proxy", {})["api_key"] = key

    _settings = Settings(**data)
    return _settings


def get_settings() -> Settings:
    return load_settings()
