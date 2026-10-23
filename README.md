# Marketing Ops MCP

[![Tests](https://github.com/ABharadwaj-cell/marketing-ops-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ABharadwaj-cell/marketing-ops-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Original Python tools for evidence-first marketing work through **ChatGPT-compatible MCP**, **OpenAI Responses agents**, or a local CLI. Version 0.1.0 is an independently implemented alpha release; it is not a fork, a renamed Claude project, or a claim of feature parity with larger reference projects.

## Working capabilities

- `calculate_funnel`: explicit-denominator conversion rates, cost per lead, media cost per customer and ROAS.
- `reconcile_transactions`: exact-ID outer join with decimal arithmetic, duplicate detection and attribution-scope gates.
- `design_experiment`: two-proportion, fixed-horizon sample-size approximation.
- `analyze_experiment`: sample-ratio checks, stopping-horizon gate, sparse-data gate and two-sided comparison.
- `build_campaign_url`: normalized UTM parameters with explicit replacement and query preservation.

These are analysis tools, not CRM connectors or autonomous campaign operators. They do not infer incrementality, fully loaded CAC from media spend, lifetime value from one period, or causal attribution. Experiment assumptions and approximation limitations are included in results.

## Run the offline example

Python 3.11+ is required. No API key is needed for this example.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
marketing-ops-mcp tools
marketing-ops-mcp run calculate_funnel examples/demo.json --out output/demo
pytest -q
ruff check .
```

The command creates `report.json`, `report.csv`, `report.md` and an escaped `report.html`. JSON contains the complete structured result; CSV contains tabular findings or metrics when available. No output is published automatically. Inputs are validated and bounded. Errors fail explicitly instead of producing invented success.

## Use with ChatGPT and OpenAI

```sh
marketing-ops-mcp serve
# Local HTTP endpoint: http://127.0.0.1:8765/mcp
marketing-ops-mcp serve --transport streamable-http
# Requires OPENAI_API_KEY and OPENAI_MODEL in your environment:
marketing-ops-mcp agent examples/task.txt --out output/agent
```

See [ChatGPT connection instructions](docs/CHATGPT.md). A ChatGPT connection needs a reachable endpoint or supported tunnel; this repository is not already hosted or connected to your account. The local HTTP service has no application authentication and must not be exposed directly. Deterministic MCP tools need no OpenAI key. The agent runner is optional and makes billable API calls.

## Repository layout

| Path | Purpose |
|---|---|
| `src/marketing_ops/tools.py` | Typed tool registry and domain entry points |
| `src/marketing_ops/agent.py` | Bounded Responses function-calling loop |
| `src/marketing_ops/server.py` | Official MCP SDK server |
| `src/marketing_ops/reports.py` | Safe, portable deliverables |
| `examples/` | Synthetic inputs and agent task |
| `tests/` | Domain, export, agent and real MCP protocol tests |
| `docs/` | Architecture, integration, validation and research |

## Quality and scope

Tests cover important numerical, validation and trust boundaries, including a real MCP stdio discovery/call round trip. OpenAI agent tests use a fake client; they do not prove live model quality. CI runs tests, lint and dependency auditing across Python 3.11–3.13. See [validation](docs/VALIDATION.md) for the recorded local result and untested deployment boundaries.

This release prioritizes inspectable behavior over code volume. It does not claim to equal the references' line counts or broad feature sets. [Scope and research](docs/RESEARCH.md) explains the conceptual inspiration and remaining gaps. Source implementation was written independently; reference README descriptions informed the problem selection.

Read [SECURITY.md](SECURITY.md) before deployment. Contributions follow [CONTRIBUTING.md](CONTRIBUTING.md) and the [community conduct policy](CODE_OF_CONDUCT.md). Licensed under [MIT](LICENSE).
