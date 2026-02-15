# lmstudio-agent-config

`lmstudio-agent-config` discovers models from LM Studio and generates local
agent configuration for common developer clients.

Supported targets:
- VS Code Copilot (`github.copilot.chat.customOAIModels`)
- OpenCode (`opencode.json`)
- Pi (`models.json`)
- Codex (`config.toml`)

It uses LM Studio model metadata from `/api/v1/models`, applies optional model
filters, then either prints a model list or writes target config files.

## Install

From source:

```bash
uv tool install .
```

From GitHub:

```bash
uvx --from git+https://github.com/alessandrobologna/lmstudio-agent-config lmstudio-agent-config --help
```

## Requirements

- LM Studio is running
- Local server is enabled in LM Studio
- The model listing endpoint is reachable (default:
  `http://localhost:1234/api/v1/models`)

## Quick start

List discovered models:

```bash
lmstudio-agent-config
```

Write config for one target:

```bash
lmstudio-agent-config --settings code
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

These filters apply to both model listing and generated settings outputs.

### VS Code

```bash
lmstudio-agent-config --settings code
lmstudio-agent-config --settings code-insiders
```

### OpenCode

```bash
lmstudio-agent-config --settings opencode
lmstudio-agent-config --settings opencode --settings-path "~/Documents/opencode.json"
```

### Pi

```bash
lmstudio-agent-config --settings pi
lmstudio-agent-config --settings pi --settings-path "~/Documents/models.json"
```

### Codex

```bash
lmstudio-agent-config --settings codex
lmstudio-agent-config --settings codex --settings-path "~/Documents/config.toml"
```

For Codex, the tool also generates one profile per discovered LM Studio model
under `profiles.*`, so you can switch models with:

```bash
codex --profile lmstudio-your-model
```

Codex does not show these generated LM Studio profiles in a model picker, so
use `--profile` explicitly when you want a non-default LM Studio model.

It does not change top-level `model_provider`, so your default provider stays as-is.

Use a custom LM Studio URL:

```bash
lmstudio-agent-config --base-url http://localhost:1234/v1
```

## Safety behavior

When writing files, the tool:
- previews a focused diff
- asks for confirmation (`y/N`)
- creates dated backups before modifying files

## License

MIT
