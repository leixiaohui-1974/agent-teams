from __future__ import annotations

from click.testing import CliRunner

from agent_teams import config as config_module
from agent_teams.cli import main


def test_routes_command_shows_active_policy(tmp_path):
    config_module._settings = None
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(
        """
execution:
  backend: "api"
  default_route: "cliproxyapi"
  fallback_routes: ["aicode"]
  parallel: true
  max_parallel: 4
routes:
  cliproxyapi:
    base_url: "http://proxy.example"
    api_key: "proxy-key"
  aicode:
    base_url: ""
    api_key: ""
""".strip(),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["--config", str(config_path), "routes"])

    assert result.exit_code == 0
    assert "Default route:" in result.output
    assert "cliproxyapi" in result.output
    assert "Fallback routes:" in result.output
    assert "aicode" in result.output
    assert "configured" in result.output
    assert "missing" in result.output
