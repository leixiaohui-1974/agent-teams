from __future__ import annotations

from pathlib import Path

from agent_teams.config import load_settings


def test_default_route_sequence_prefers_cliproxyapi(tmp_path, monkeypatch):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
proxy:
  base_url: "http://legacy.example"
  api_key: "legacy-key"
routes:
  cliproxyapi:
    base_url: "http://proxy.example"
    api_key: "proxy-key"
execution:
  default_route: "cliproxyapi"
  fallback_routes: ["aicode"]
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.delenv("AGENT_TEAMS_ROUTE_DEFAULT", raising=False)
    settings = load_settings(config_path)

    assert settings.get_route_sequence() == ["cliproxyapi", "aicode"]
    assert settings.resolve_route("cliproxyapi").base_url == "http://proxy.example"


def test_proxy_env_populates_unified_cliproxy_route(tmp_path, monkeypatch):
    config_path = tmp_path / "settings.yaml"
    config_path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("AGENT_TEAMS_PROXY_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("AGENT_TEAMS_API_KEY", "secret")

    settings = load_settings(config_path)

    assert settings.resolve_route("cliproxyapi").base_url == "http://127.0.0.1:9000"
    assert settings.resolve_route("cliproxyapi").api_key == "secret"
