"""Model selection strategy per agent role."""
from __future__ import annotations

from agent_teams.config import get_settings
from agent_teams.core.client import get_client


async def pick_model_for_role(role: str) -> str:
    """Select the best available model for a given agent role."""
    settings = get_settings()
    agent_cfg = settings.agents.get(role)
    preferences = agent_cfg.models if agent_cfg else []
    if not preferences:
        preferences = ["claude-sonnet-4-20250514", "gpt-4o", "gemini-2.5-flash"]
    client = get_client()
    return await client.pick_model(preferences)


def get_temperature_for_role(role: str) -> float:
    settings = get_settings()
    agent_cfg = settings.agents.get(role)
    return agent_cfg.temperature if agent_cfg else 0.5
