# lmstudio-agent-config

[![CI](https://github.com/alessandrobologna/lmstudio-agent-config/actions/workflows/ci.yml/badge.svg)](https://github.com/alessandrobologna/lmstudio-agent-config/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/lmstudio-agent-config)](https://pypi.org/project/lmstudio-agent-config/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

`lmstudio-agent-config` discovers models from [LM Studio](https://lmstudio.ai) and generates local
agent configuration for common developer clients.

Supported targets:
- [VS Code](https://code.visualstudio.com) + [GitHub Copilot](https://github.com/features/copilot)
- [OpenCode](https://opencode.ai)
- [Pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent)
- [Codex](https://openai.com/codex)

## About

This tool reads LM Studio’s `/api/v1/models` endpoint, detects model capabilities, and produces
client-specific configuration. You can print a model list or write config files directly for the
supported targets, with optional filters for context length and capabilities.

## Features

- Auto-discover LM Studio models from `/api/v1/models`.
- Detect tool calling, vision support, and context length.
- Generate configs for VS Code Copilot, OpenCode, Pi, and Codex.
- Preview changes with a focused diff and a confirmation prompt.
- Create dated backups before writing files.
- Filter by minimum context length, tools, and vision support.

## How it works

- Queries LM Studio’s local server for available models.
- Builds target-specific configuration payloads.
- Either prints results or updates config files in place.

## Safety behavior

When writing files, the tool is intentionally conservative. It prints a focused diff of only the
changed lines, asks for confirmation (`y/N`), and only then writes the file. Before any modification,
it creates a dated backup next to the original file (for example:
`settings.260215-0.backup.json`), so you can roll back easily if needed.

## Install

Run without install (PyPI):

```bash
uvx lmstudio-agent-config --help
```

Install with pip:

```bash
pip install lmstudio-agent-config
```

From source:

```bash
uv tool install .
```

## Requirements

- LM Studio is running.
- The local server is enabled in LM Studio.
- The model listing endpoint is reachable (default: `http://localhost:1234/api/v1/models`).
- If LM Studio runs on another machine, use `--base-url` to point at that host and port.

## Quick start

List discovered models:

```bash
lmstudio-agent-config
```

Write config for one target:

```bash
lmstudio-agent-config --settings code
```

Use a remote LM Studio server:

```bash
lmstudio-agent-config --base-url http://LMSTUDIO_HOST:1234/v1
```

Update all installed targets at once (skips missing default files):

```bash
lmstudio-agent-config --settings all
```

## Usage

Use filters to control which models are included:

```bash
lmstudio-agent-config --min-context 32768
lmstudio-agent-config --tools
lmstudio-agent-config --no-tools
lmstudio-agent-config --vision
lmstudio-agent-config --no-vision
lmstudio-agent-config --min-context 32768 --tools --vision
```

### Targets and default paths

Use `--settings-path` to override any default path.

| Target | Flag | Default path |
| --- | --- | --- |
| VS Code | `--settings code` | `~/Library/Application Support/Code/User/settings.json` |
| VS Code Insiders | `--settings code-insiders` | `~/Library/Application Support/Code - Insiders/User/settings.json` |
| OpenCode | `--settings opencode` | `~/.opencode/opencode.json` |
| Pi | `--settings pi` | `~/.pi/agent/models.json` |
| Codex | `--settings codex` | `~/.codex/config.toml` |

### Codex profiles

For Codex, the tool also generates one profile per discovered LM Studio model under `profiles.*`.
Switch models with:

```bash
codex --profile lmstudio-your-model
```

Codex does not show these generated LM Studio profiles in a model picker, so use `--profile`
explicitly when you want a non-default LM Studio model. The tool does not change top-level
`model_provider`, so your default provider stays as-is.

### Custom base URL

Use a custom LM Studio URL:

```bash
lmstudio-agent-config --base-url http://localhost:1234/v1
```

If LM Studio runs on another machine, you must point `--base-url` at that host and port.

## Contributing

Issues and pull requests are welcome. For local development:

```bash
git clone https://github.com/alessandrobologna/lmstudio-agent-config.git
cd lmstudio-agent-config
uv sync --extra dev
uv run pytest
uv run ruff format --check
uv run ruff check
uv run ty check
```

If you want reproducible dev installs, use `uv sync --extra dev --frozen`.

## License

MIT
