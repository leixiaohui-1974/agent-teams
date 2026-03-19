# Agent Teams Three-Engine Upgrade

Date: 2026-03-19

## What Changed

- Unified the repository around an API-first execution policy.
- Default route is now `cliproxyapi`.
- `subscription` and `aicode` remain available as upstream concepts, but the repository treats `cliproxyapi` as the primary shared entry.
- Added route-aware configuration in `agent_teams/settings.yaml`.
- Added automatic route fallback support in the HTTP client.
- Added stage-based parallel workflow execution with higher default concurrency.
- Added a CLI route inspection command: `ai routes`.

## Runtime Policy

- Backend: `api`
- Default route: `cliproxyapi`
- Fallback routes: none by default
- Parallel execution: enabled
- Max parallel workers: `6`

## Why This Matches The Local Three-Engine Setup

- Codex, Claude, and Gemini can still be assigned fixed functional roles through `settings.yaml`.
- The repository no longer assumes a single raw proxy URL.
- The main runtime path is now aligned with the local preference:
  - prefer API
  - allow a unified proxy/gateway entry
  - support more concurrent lanes/terminals

## Files Updated

- `agent_teams/config.py`
- `agent_teams/core/client.py`
- `agent_teams/workflows/base.py`
- `agent_teams/coding/workflows/all_workflows.py`
- `agent_teams/publishing/workflows/all_workflows.py`
- `agent_teams/cli.py`
- `agent_teams/settings.yaml`

## Verification

- Added route configuration tests.
- Added workflow parallelism test.
