# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "click",
#     "click-help-colors",
#     "json5",
#     "rich",
#     "tomli-w",
#     "tomli; python_version < '3.11'",
# ]
# ///
"""
LM Studio Config Generator for GitHub Copilot, OpenCode, Pi, and Codex

This script automatically discovers LLM models from your LM Studio instance
and generates configuration for:
- GitHub Copilot's custom OpenAI models feature (VS Code settings.json)
- OpenCode's opencode.json provider config
- Pi's models.json provider config
- Codex's config.toml provider config

Features:
- Auto-discovery of all available LLM models
- Proper capability detection (tool calling, context length)
- Direct VS Code settings.json update support
- OpenCode opencode.json update support
- Cross-platform compatibility (macOS, Windows, Linux)
- JSONC format support (handles comments and trailing commas)

Usage:
    # Run with uvx (no install required)
    uvx --from git+https://github.com/alessandrobologna/lmstudio-agent-config lmstudio-agent-config --help

    # Or install and run
    pip install git+https://github.com/alessandrobologna/lmstudio-agent-config
    lmstudio-agent-config --help

Repository: https://github.com/alessandrobologna/lmstudio-agent-config
Author: Alessandro Bologna
License: MIT
"""
import requests
import json
import json5
import click
import shutil
import platform
import difflib
import sys
import os
import re
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse
import tomli_w
from click_help_colors import HelpColorsCommand
from rich.console import Console
from rich.text import Text

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

def get_vscode_settings_path(editor_type):
    """Get the settings.json path for VS Code or VS Code Insiders based on OS."""
    system = platform.system()
    home = Path.home()

    if editor_type == "code":
        if system == "Darwin":  # macOS
            return home / "Library/Application Support/Code/User/settings.json"
        elif system == "Windows":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Code/User/settings.json"
        else:  # Linux and others
            return home / ".config/Code/User/settings.json"
    elif editor_type == "code-insiders":
        if system == "Darwin":  # macOS
            return home / "Library/Application Support/Code - Insiders/User/settings.json"
        elif system == "Windows":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Code - Insiders/User/settings.json"
        else:  # Linux and others
            return home / ".config/Code - Insiders/User/settings.json"
    else:
        raise ValueError(f"Unknown editor type: {editor_type}")

def get_opencode_settings_path():
    """Get the default opencode.json path."""
    home = Path.home()
    return home / ".opencode" / "opencode.json"

def get_pi_models_path():
    """Get the default Pi models.json path."""
    home = Path.home()
    return home / ".pi" / "agent" / "models.json"

def get_codex_config_path():
    """Get the default Codex config.toml path."""
    home = Path.home()
    return home / ".codex" / "config.toml"

def get_settings_target_path(setting):
    """Resolve default path for a known settings target."""
    if setting == "opencode":
        return get_opencode_settings_path()
    if setting == "pi":
        return get_pi_models_path()
    if setting == "codex":
        return get_codex_config_path()
    return get_vscode_settings_path(setting)

def detect_indentation(content):
    """Detect the indentation style from existing content."""
    for line in content.splitlines():
        if line and (line[0] == ' ' or line[0] == '\t'):
            # Found an indented line, extract the leading whitespace
            indent = ''
            for char in line:
                if char in (' ', '\t'):
                    indent += char
                else:
                    break
            if indent:
                return len(indent)
    # Default to 2 spaces if we can't detect
    return 2

def normalize_openai_base_url(url):
    """Ensure base URL ends with /v1 for OpenAI-compatible endpoints."""
    base = url.rstrip('/')
    if base.endswith('/v1'):
        return base
    return f"{base}/v1"

def show_diff_and_confirm(old_content, new_content, file_path):
    """Show diff between old and new content and ask for confirmation.

    Returns: 'unchanged', 'apply', or 'cancel'.
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # Use ndiff but only keep changed lines (+/-), mirroring the Rust behavior.
    diff = list(difflib.ndiff(old_lines, new_lines))
    changes = [line for line in diff if line and line[0] in ('+', '-')]

    if not changes:
        print("No changes detected.")
        return 'unchanged'

    print(f"\nDiff preview for: {file_path}\n")
    for line in changes:
        if line[0] == '+':
            # Green for additions
            print(f"\033[32m{line}\033[0m", end='')
        elif line[0] == '-':
            # Red for deletions
            print(f"\033[31m{line}\033[0m", end='')
    print()

    # Ask for confirmation
    response = input("\nApply these changes? [y/N]: ").strip().lower()
    if response in ['y', 'yes']:
        return 'apply'
    return 'cancel'

def fetch_models(api_base):
    resp = requests.get(api_base)
    resp.raise_for_status()
    payload = resp.json()

    if isinstance(payload.get("models"), list):
        return payload["models"]

    raise ValueError("Unexpected model list response format: expected 'models' array")

def get_model_id(model):
    """Get model identifier from v1 (`key`) payloads."""
    return model.get("key")

def model_supports_tool_calling(model):
    """Detect tool calling from v1 capabilities object."""
    capabilities = model.get("capabilities")
    if isinstance(capabilities, dict):
        return bool(capabilities.get("trained_for_tool_use"))
    return False

def model_supports_vision(model):
    """Detect vision support from v1 capabilities object."""
    capabilities = model.get("capabilities")
    if isinstance(capabilities, dict):
        return bool(capabilities.get("vision"))
    return False

def model_matches_filters(model, min_context=None, tools_filter="any", vision_filter="any"):
    """Check whether a model matches active filters."""
    if min_context is not None:
        max_context = model.get("max_context_length")
        if not isinstance(max_context, int) or max_context < min_context:
            return False

    has_tools = model_supports_tool_calling(model) if model.get("type") == "llm" else False
    if tools_filter == "required" and not has_tools:
        return False
    if tools_filter == "exclude" and has_tools:
        return False

    has_vision = model_supports_vision(model) if model.get("type") == "llm" else False
    if vision_filter == "required" and not has_vision:
        return False
    if vision_filter == "exclude" and has_vision:
        return False

    return True

def filter_models(models, min_context=None, tools_filter="any", vision_filter="any"):
    """Filter a model list according to the active CLI filters."""
    return [
        model
        for model in models
        if model_matches_filters(
            model,
            min_context=min_context,
            tools_filter=tools_filter,
            vision_filter=vision_filter,
        )
    ]

def render_models_table(api_base, min_context=None, tools_filter="any", vision_filter="any"):
    """Render discovered models as a rich, human-readable list."""
    all_models = fetch_models(api_base)
    models = filter_models(
        all_models,
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    rows = []
    llm_count = 0
    tools_count = 0
    vision_count = 0

    llm_ids = []
    for model in models:
        if model.get("type") != "llm":
            continue
        model_id = get_model_id(model)
        if not model_id:
            continue
        llm_ids.append(model_id)
        if model_supports_tool_calling(model):
            tools_count += 1
        if model_supports_vision(model):
            vision_count += 1

    profile_by_model = {}
    for profile_name, profile in generate_codex_profiles(llm_ids, "lmstudio_local").items():
        model_id = profile.get("model")
        if isinstance(model_id, str):
            profile_by_model[model_id] = profile_name

    for model in models:
        model_id = get_model_id(model) or "<unknown>"
        model_type = str(model.get("type") or "?")
        max_context = model.get("max_context_length")
        context = str(max_context) if isinstance(max_context, int) else "-"

        if model_type == "llm":
            llm_count += 1
            tools_yes = model_supports_tool_calling(model)
            vision_yes = model_supports_vision(model)
            profile_name = profile_by_model.get(model_id, "-")
        else:
            tools_yes = None
            vision_yes = None
            profile_name = "-"

        rows.append(
            {
                "model_id": model_id,
                "type": model_type,
                "context": context,
                "tools_yes": tools_yes,
                "vision_yes": vision_yes,
                "profile": profile_name,
                "llm_first": 0 if model_type == "llm" else 1,
            }
        )

    rows.sort(key=lambda r: (r["llm_first"], r["model_id"]))
    console = Console()

    if not rows:
        console.print("No models matched the selected filters.")
        return

    console.print("[bold]LM Studio Models[/bold]")
    console.print(f"- showing: [bold]{len(rows)}[/] of [bold]{len(all_models)}[/]")
    console.print(f"- llm: [bold]{llm_count}[/]")
    console.print(f"- tool-use: [bold]{tools_count}[/]")
    console.print(f"- vision: [bold]{vision_count}[/]")
    filters_label = (
        f"min-context={min_context if min_context is not None else 'any'}, "
        f"tools={tools_filter}, vision={vision_filter}"
    )
    console.print(f"- filters: [bold]{filters_label}[/]")
    console.print("")

    llm_rows = [row for row in rows if row["type"] == "llm"]
    other_rows = [row for row in rows if row["type"] != "llm"]

    if llm_rows:
        console.print("[bold]LLM Models[/bold]")
    for row in llm_rows:
        title = Text("- ")
        title.append(row["model_id"], style="bold")
        console.print(title)

        details = Text("  type: ", style="dim")
        details.append(row["type"], style="magenta")
        details.append(" | context: ", style="dim")
        details.append(row["context"], style="yellow" if row["context"] != "-" else "dim")
        details.append(" | tools: ", style="dim")
        details.append("yes" if row["tools_yes"] else "no", style="green" if row["tools_yes"] else "dim")
        details.append(" | vision: ", style="dim")
        details.append("yes" if row["vision_yes"] else "no", style="green" if row["vision_yes"] else "dim")
        console.print(details)

        profile_line = Text("  codex-profile: ", style="dim")
        profile_line.append(row["profile"], style="cyan")
        console.print(profile_line)

    if llm_rows and other_rows:
        console.print("")
    if other_rows:
        console.print("[bold]Other Models[/bold]")
    for row in other_rows:
        title = Text("- ")
        title.append(row["model_id"])
        console.print(title)

        details = Text("  type: ", style="dim")
        details.append(row["type"], style="dim")
        details.append(" | context: ", style="dim")
        details.append(row["context"], style="dim")
        details.append(" | tools: ", style="dim")
        details.append("-", style="dim")
        details.append(" | vision: ", style="dim")
        details.append("-", style="dim")
        console.print(details)

    console.print("")
    console.print("[dim]Tip:[/] run [cyan]codex --profile <name>[/cyan] to switch LM Studio models.")

def codex_profile_name_for_model(model_id, used_names, prefix="lmstudio"):
    """Generate a stable, CLI-friendly profile name for a model id."""
    slug = re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")
    if not slug:
        slug = "model"
    base = f"{prefix}-{slug}"

    name = base
    index = 2
    while name in used_names:
        name = f"{base}-{index}"
        index += 1

    used_names.add(name)
    return name

def generate_codex_profiles(model_ids, provider_id):
    """Generate one Codex profile per LM Studio model."""
    used_names = set()
    profiles = {}
    for model_id in sorted(set(model_ids)):
        profile_name = codex_profile_name_for_model(model_id, used_names)
        profiles[profile_name] = {
            "model": model_id,
            "model_provider": provider_id,
        }
    return profiles

def generate_copilot_config(api_base, openai_url, min_context=None, tools_filter="any", vision_filter="any"):
    models = filter_models(
        fetch_models(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    config = {}
    for model in models:
        # Only include LLM models, skip embeddings and other types
        if model.get("type") != "llm":
            continue
            
        model_id = get_model_id(model)
        if not model_id:
            continue
        max_context = model.get("max_context_length", 8192)
        
        # Insert fields; we'll normalize key order below
        config[model_id] = {
            "name": model_id,
            "url": openai_url,
            "toolCalling": model_supports_tool_calling(model),
            "vision": model_supports_vision(model),
            "thinking": True,  # Default to True, can be customized per model
            "maxInputTokens": max_context,
            "maxOutputTokens": max_context,
            "requiresAPIKey": False,
        }

    if not config:
        raise ValueError("No LLM models matched the selected filters.")

    # Sort models by id for stable ordering (to match Rust BTreeMap),
    # and sort fields alphabetically within each model (to match serde_json Map)
    ordered: dict[str, dict] = {}
    for model_id in sorted(config.keys()):
        v = config[model_id]
        ordered[model_id] = OrderedDict(sorted(v.items(), key=lambda item: item[0]))

    return ordered

def generate_opencode_provider(
    api_base,
    base_url,
    provider_id="lmstudio",
    provider_name="LM Studio (local)",
    min_context=None,
    tools_filter="any",
    vision_filter="any",
):
    models = filter_models(
        fetch_models(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    config = {}
    for model in models:
        # Only include LLM models, skip embeddings and other types
        if model.get("type") != "llm":
            continue

        model_id = get_model_id(model)
        if not model_id:
            continue
        max_context = model.get("max_context_length", 8192)
        has_vision = model_supports_vision(model)

        config[model_id] = {
            "name": model_id,
            "limit": {
                "context": max_context,
                "output": max_context,
            },
        }
        if has_vision:
            config[model_id]["modalities"] = {"input": ["text", "image"], "output": ["text"]}
        else:
            config[model_id]["modalities"] = {"input": ["text"], "output": ["text"]}

    if not config:
        raise ValueError("No LLM models matched the selected filters.")

    ordered_models: dict[str, dict] = {}
    for model_id in sorted(config.keys()):
        ordered_models[model_id] = config[model_id]

    provider = {
        "npm": "@ai-sdk/openai-compatible",
        "name": provider_name,
        "options": {
            "baseURL": normalize_openai_base_url(base_url),
        },
        "models": ordered_models,
    }

    return provider_id, provider

def generate_pi_provider(
    api_base,
    base_url,
    provider_id="lmstudio",
    min_context=None,
    tools_filter="any",
    vision_filter="any",
):
    models = filter_models(
        fetch_models(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    config = []
    for model in models:
        # Pi expects LLM models for chat providers.
        if model.get("type") != "llm":
            continue

        model_id = get_model_id(model)
        if not model_id:
            continue
        max_context = model.get("max_context_length", 8192)
        has_vision = model_supports_vision(model)

        entry = {
            "id": model_id,
            "name": model_id,
            "input": ["text", "image"] if has_vision else ["text"],
            "contextWindow": max_context,
            "maxTokens": max_context,
        }
        config.append(entry)

    if not config:
        raise ValueError("No LLM models matched the selected filters.")

    ordered_models = sorted(config, key=lambda model: model["id"])

    provider = {
        "baseUrl": normalize_openai_base_url(base_url),
        "api": "openai-completions",
        "apiKey": "lm-studio",
        "models": ordered_models,
    }

    return provider_id, provider

def generate_codex_config(
    api_base,
    base_url,
    provider_id="lmstudio_local",
    provider_name="LM Studio (local)",
    min_context=None,
    tools_filter="any",
    vision_filter="any",
):
    models = filter_models(
        fetch_models(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    llm_ids = []
    for model in models:
        if model.get("type") != "llm":
            continue
        model_id = get_model_id(model)
        if model_id:
            llm_ids.append(model_id)

    if not llm_ids:
        raise ValueError("No LLM models matched the selected filters.")

    provider = {
        "name": provider_name,
        "base_url": normalize_openai_base_url(base_url),
        "wire_api": "responses",
    }

    return {
        "model_providers": {
            provider_id: provider,
        },
        "profiles": generate_codex_profiles(llm_ids, provider_id),
    }

def update_opencode_file(opencode_path, provider_id, provider):
    """Update opencode.json with the generated provider configuration."""
    opencode_file = Path(opencode_path).expanduser()

    # Read existing content
    old_content = ""
    if opencode_file.exists():
        try:
            with open(opencode_file, 'r', encoding='utf-8') as f:
                old_content = f.read()
            opencode_config = json5.loads(old_content)
        except Exception as e:
            print(f"Warning: Could not parse existing opencode config ({e}), creating new structure...")
            opencode_config = {}
    else:
        opencode_config = {}

    # Detect original indentation
    indent = detect_indentation(old_content) if old_content else 2

    if not isinstance(opencode_config, dict):
        print("Warning: opencode config is not a JSON object, overwriting with new structure...")
        opencode_config = {}

    opencode_config.setdefault("$schema", "https://opencode.ai/config.json")

    providers = opencode_config.get("provider", {})
    if not isinstance(providers, dict):
        providers = {}

    existing_provider = providers.get(provider_id, {})
    if not isinstance(existing_provider, dict):
        existing_provider = {}

    merged_provider = dict(existing_provider)
    merged_provider["npm"] = provider.get("npm")
    merged_provider["name"] = provider.get("name")

    existing_options = existing_provider.get("options", {})
    if not isinstance(existing_options, dict):
        existing_options = {}
    merged_options = dict(existing_options)
    merged_options["baseURL"] = provider.get("options", {}).get("baseURL")
    merged_provider["options"] = merged_options

    merged_provider["models"] = provider.get("models", {})
    providers[provider_id] = merged_provider
    opencode_config["provider"] = providers

    new_content = json.dumps(opencode_config, indent=indent)

    decision = show_diff_and_confirm(old_content, new_content, str(opencode_file))
    if decision == 'unchanged':
        return
    if decision == 'cancel':
        print("Operation cancelled by user")
        sys.exit(0)

    if not opencode_file.parent.exists():
        opencode_file.parent.mkdir(parents=True, exist_ok=True)

    if opencode_file.exists():
        from datetime import datetime

        date_tag = datetime.now().strftime("%y%m%d")
        stem = opencode_file.stem or "opencode"

        index = 0
        while True:
            backup_name = f"{stem}.{date_tag}-{index}.backup.json"
            backup_path = opencode_file.with_name(backup_name)
            if not backup_path.exists():
                break
            index += 1

        shutil.copy2(opencode_file, backup_path)
        print(f"Created backup at {backup_path}")

    with open(opencode_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Successfully updated {opencode_file} with {len(provider.get('models', {}))} models")

def update_pi_file(pi_path, provider_id, provider):
    """Update Pi models.json with the generated provider configuration."""
    pi_file = Path(pi_path).expanduser()

    old_content = ""
    if pi_file.exists():
        try:
            with open(pi_file, 'r', encoding='utf-8') as f:
                old_content = f.read()
            pi_config = json5.loads(old_content)
        except Exception as e:
            print(f"Warning: Could not parse existing Pi config ({e}), creating new structure...")
            pi_config = {}
    else:
        pi_config = {}

    indent = detect_indentation(old_content) if old_content else 2

    if not isinstance(pi_config, dict):
        print("Warning: Pi config is not a JSON object, overwriting with new structure...")
        pi_config = {}

    providers = pi_config.get("providers", {})
    if not isinstance(providers, dict):
        providers = {}

    existing_provider = providers.get(provider_id, {})
    if not isinstance(existing_provider, dict):
        existing_provider = {}

    merged_provider = dict(existing_provider)
    merged_provider["baseUrl"] = provider.get("baseUrl")
    merged_provider["api"] = provider.get("api")
    merged_provider["apiKey"] = provider.get("apiKey")
    merged_provider["models"] = provider.get("models", [])

    providers[provider_id] = merged_provider
    pi_config["providers"] = providers

    new_content = json.dumps(pi_config, indent=indent)

    decision = show_diff_and_confirm(old_content, new_content, str(pi_file))
    if decision == 'unchanged':
        return
    if decision == 'cancel':
        print("Operation cancelled by user")
        sys.exit(0)

    if not pi_file.parent.exists():
        pi_file.parent.mkdir(parents=True, exist_ok=True)

    if pi_file.exists():
        from datetime import datetime

        date_tag = datetime.now().strftime("%y%m%d")
        stem = pi_file.stem or "models"

        index = 0
        while True:
            backup_name = f"{stem}.{date_tag}-{index}.backup.json"
            backup_path = pi_file.with_name(backup_name)
            if not backup_path.exists():
                break
            index += 1

        shutil.copy2(pi_file, backup_path)
        print(f"Created backup at {backup_path}")

    with open(pi_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Successfully updated {pi_file} with {len(provider.get('models', []))} models")

def update_codex_file(codex_path, codex_config):
    """Update Codex config.toml with the generated provider configuration."""
    codex_file = Path(codex_path).expanduser()

    old_content = ""
    if codex_file.exists():
        try:
            with open(codex_file, 'r', encoding='utf-8') as f:
                old_content = f.read()
            parsed = tomllib.loads(old_content)
        except Exception as e:
            print(f"Warning: Could not parse existing Codex config ({e}), creating new structure...")
            parsed = {}
    else:
        parsed = {}

    if not isinstance(parsed, dict):
        print("Warning: Codex config is not a TOML object, overwriting with new structure...")
        parsed = {}

    merged = dict(parsed)

    providers = merged.get("model_providers", {})
    if not isinstance(providers, dict):
        providers = {}

    providers_update = codex_config.get("model_providers", {})
    if not isinstance(providers_update, dict) or not providers_update:
        raise ValueError("Invalid generated Codex config: missing model_providers")

    for provider_id, provider_update in providers_update.items():
        if not isinstance(provider_update, dict):
            continue
        existing_provider = providers.get(provider_id, {})
        if not isinstance(existing_provider, dict):
            existing_provider = {}

        merged_provider = dict(existing_provider)
        merged_provider["name"] = provider_update.get("name")
        merged_provider["base_url"] = provider_update.get("base_url")
        merged_provider["wire_api"] = provider_update.get("wire_api")
        providers[provider_id] = merged_provider

    merged["model_providers"] = providers

    profiles = merged.get("profiles", {})
    if not isinstance(profiles, dict):
        profiles = {}

    profiles_update = codex_config.get("profiles", {})
    if not isinstance(profiles_update, dict):
        profiles_update = {}

    # Prune stale generated LM Studio profiles when filters narrow the model set.
    # This mirrors the behavior of other targets where generated model lists are replaced.
    managed_prefix = "lmstudio-"
    stale_profile_names = [
        profile_name
        for profile_name, profile in profiles.items()
        if isinstance(profile, dict)
        and profile.get("model_provider") in providers_update.keys()
        and profile_name.startswith(managed_prefix)
        and profile_name not in profiles_update
    ]
    for profile_name in stale_profile_names:
        del profiles[profile_name]

    for profile_name, profile_update in profiles_update.items():
        if not isinstance(profile_update, dict):
            continue
        existing_profile = profiles.get(profile_name, {})
        if not isinstance(existing_profile, dict):
            existing_profile = {}

        merged_profile = dict(existing_profile)
        merged_profile["model"] = profile_update.get("model")
        merged_profile["model_provider"] = profile_update.get("model_provider")
        profiles[profile_name] = merged_profile

    merged["profiles"] = profiles

    new_content = tomli_w.dumps(merged)

    decision = show_diff_and_confirm(old_content, new_content, str(codex_file))
    if decision == 'unchanged':
        return
    if decision == 'cancel':
        print("Operation cancelled by user")
        sys.exit(0)

    if not codex_file.parent.exists():
        codex_file.parent.mkdir(parents=True, exist_ok=True)

    if codex_file.exists():
        from datetime import datetime

        date_tag = datetime.now().strftime("%y%m%d")
        stem = codex_file.stem or "config"

        index = 0
        while True:
            backup_name = f"{stem}.{date_tag}-{index}.backup.toml"
            backup_path = codex_file.with_name(backup_name)
            if not backup_path.exists():
                break
            index += 1

        shutil.copy2(codex_file, backup_path)
        print(f"Created backup at {backup_path}")

    with open(codex_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    provider_ids = ", ".join(sorted(providers_update.keys()))
    print(
        f"Successfully updated {codex_file} with provider(s) '{provider_ids}' "
        f"and {len(profiles_update)} profiles"
    )

def update_settings_file(settings_path, config):
    """Update the settings.json file with the new model configuration."""
    settings_file = Path(settings_path).expanduser()

    # Read existing content
    old_content = ""
    if settings_file.exists():
        try:
            # Use json5 to parse JSONC files (handles comments and trailing commas)
            with open(settings_file, 'r', encoding='utf-8') as f:
                old_content = f.read()

            settings = json5.loads(old_content)

        except Exception as e:
            # If parsing fails, create a minimal settings structure
            print(f"Warning: Could not parse existing settings ({e}), creating new structure...")
            settings = {}
    else:
        settings = {}

    # Detect original indentation
    indent = detect_indentation(old_content) if old_content else 2

    # Update the customOAIModels section
    settings["github.copilot.chat.customOAIModels"] = config

    # Generate new content with original indentation
    new_content = json.dumps(settings, indent=indent)

    # Show diff and ask for confirmation
    decision = show_diff_and_confirm(old_content, new_content, str(settings_file))
    if decision == 'unchanged':
        # Nothing to do, leave file and backups untouched.
        return
    if decision == 'cancel':
        print("Operation cancelled by user")
        sys.exit(0)

    # Create dated backup before modifying, e.g. settings.250924-0.backup.json
    if settings_file.exists():
        from datetime import datetime

        date_tag = datetime.now().strftime("%y%m%d")
        stem = settings_file.stem or "settings"

        index = 0
        while True:
            backup_name = f"{stem}.{date_tag}-{index}.backup.json"
            backup_path = settings_file.with_name(backup_name)
            if not backup_path.exists():
                break
            index += 1

        shutil.copy2(settings_file, backup_path)
        print(f"Created backup at {backup_path}")

    # Write back to file (as regular JSON with proper formatting)
    with open(settings_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"Successfully updated {settings_file} with {len(config)} models")


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    cls=HelpColorsCommand,
    help_headers_color="yellow",
    help_options_color="green",
)
@click.option(
    '--base-url',
    metavar='BASE_URL',
    default='http://localhost:1234/v1',
    show_default=True,
    help='Base URL to write in config (where the client will connect)',
)
@click.option(
    '--min-context',
    metavar='TOKENS',
    type=click.IntRange(min=0),
    default=None,
    help='Only include models with max_context_length >= TOKENS',
)
@click.option(
    '--tools',
    'tools_required',
    is_flag=True,
    help='Only include models that support tool use',
)
@click.option(
    '--no-tools',
    'tools_excluded',
    is_flag=True,
    help='Only include models that do not support tool use',
)
@click.option(
    '--vision',
    'vision_required',
    is_flag=True,
    help='Only include models that support vision',
)
@click.option(
    '--no-vision',
    'vision_excluded',
    is_flag=True,
    help='Only include models that do not support vision',
)
@click.option(
    '--settings',
    metavar='SETTINGS',
    type=click.Choice(['code', 'code-insiders', 'opencode', 'pi', 'codex', 'all'], case_sensitive=False),
    help='Auto-detect settings path (code, code-insiders, opencode, pi, codex, all)',
)
@click.option(
    '--settings-path',
    metavar='SETTINGS_PATH',
    type=click.Path(),
    help='Path to settings file (overrides --settings auto-detect; prints a model list if neither --settings nor --settings-path is provided)',
)
def main(
    base_url,
    min_context,
    tools_required,
    tools_excluded,
    vision_required,
    vision_excluded,
    settings,
    settings_path,
):
    """
    Generate GitHub Copilot, OpenCode, Pi, or Codex configuration from LM Studio.
    
    This script automatically discovers all LLM models available in your LM Studio instance
    and generates configuration for GitHub Copilot's custom OpenAI models feature (VS Code),
    OpenCode's opencode.json provider config, Pi's models.json provider config, or Codex's
    config.toml provider config. It reads model capabilities (tool calling, context length)
    directly from the API.
    
    \b
    EXAMPLES:

    # List discovered models (default output)
    uvx --from git+https://github.com/alessandrobologna/lmstudio-agent-config lmstudio-agent-config

    # Filter model list (context + capabilities)
    lmstudio-agent-config --min-context 32768 --tools --vision

    # Use a custom LM Studio URL
    lmstudio-agent-config --base-url http://studio.local:1234/v1

    # Auto-detect and update VS Code settings (macOS)
    lmstudio-agent-config --settings code

    # Auto-detect and update VS Code Insiders settings
    lmstudio-agent-config --settings code-insiders

    # Or specify custom settings path (macOS)
    lmstudio-agent-config --settings-path "~/Library/Application Support/Code/User/settings.json"

    # Windows VS Code settings
    lmstudio-agent-config --settings-path "%APPDATA%/Code/User/settings.json"

    # Linux VS Code settings
    lmstudio-agent-config --settings-path "~/.config/Code/User/settings.json"

    # Update opencode.json at the default path (~/.opencode/opencode.json)
    lmstudio-agent-config --settings opencode

    # Update opencode.json at a custom path
    lmstudio-agent-config --settings opencode --settings-path "~/Documents/opencode.json"

    # Update Pi models.json at the default path (~/.pi/agent/models.json)
    lmstudio-agent-config --settings pi

    # Update Pi models.json at a custom path
    lmstudio-agent-config --settings pi --settings-path "~/Documents/models.json"

    # Update Codex config.toml at the default path (~/.codex/config.toml)
    lmstudio-agent-config --settings codex

    # Update Codex config.toml at a custom path
    lmstudio-agent-config --settings codex --settings-path "~/Documents/config.toml"

    # Update all known harness configs that are already installed
    # (skips missing default files)
    lmstudio-agent-config --settings all

    # Run Codex with a generated profile
    codex --profile lmstudio-your-model
    
    \b
    SETUP:
    1. Start LM Studio with your desired models loaded
    2. Run this script to generate or update your configuration
    3. If using VS Code output, restart VS Code to pick up the new models
    4. Access your local models via GitHub Copilot chat model selector
    
    For VS Code output, the script automatically detects tool calling and vision capabilities,
    context lengths, and filters out non-LLM models (like embeddings).
    All models are configured with thinking=true by default, while vision and toolCalling are
    auto-detected (adjust manually if needed). For OpenCode and Pi outputs, model limits are
    populated from the LM Studio context length. For Codex output, a custom local LM Studio
    provider is configured (`wire_api = "responses"`) and one profile per discovered model is
    generated under `profiles.*`. The tool does not modify top-level `model_provider`, so
    models can be switched explicitly with `codex --profile <name>`.
    """

    if tools_required and tools_excluded:
        raise click.UsageError("Use either --tools or --no-tools, not both.")
    if vision_required and vision_excluded:
        raise click.UsageError("Use either --vision or --no-vision, not both.")

    tools_filter = "required" if tools_required else "exclude" if tools_excluded else "any"
    vision_filter = "required" if vision_required else "exclude" if vision_excluded else "any"

    if settings == "all" and settings_path:
        raise click.UsageError("--settings-path cannot be used with --settings all.")
    
    # Determine output format
    if not settings and not settings_path:
        output_format = "models"
    elif settings == "all":
        output_format = "all"
    elif settings == "opencode":
        output_format = "opencode"
    elif settings == "pi":
        output_format = "pi"
    elif settings == "codex":
        output_format = "codex"
    else:
        output_format = "vscode"

    # Determine the settings path
    final_settings_path = None
    if settings_path:
        final_settings_path = settings_path
    elif settings and settings != "all":
        try:
            final_settings_path = str(get_settings_target_path(settings))
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(1)

    if final_settings_path:
        if output_format == "vscode":
            label = "settings file"
        elif output_format == "opencode":
            label = "opencode file"
        elif output_format == "pi":
            label = "pi models file"
        else:
            label = "codex config file"
        print(f"Using {label}: {final_settings_path}")

    # Construct API URL from the same host/port as --base-url.
    base = base_url.rstrip('/')
    if base.endswith('/v1'):
        base = base[:-3].rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme and parsed.netloc:
        api_base = f"{parsed.scheme}://{parsed.netloc}/api/v1/models"
    else:
        api_base = "http://localhost:1234/api/v1/models"
    openai_url = base_url

    try:
        if output_format == "models":
            render_models_table(
                api_base,
                min_context=min_context,
                tools_filter=tools_filter,
                vision_filter=vision_filter,
            )
        elif output_format == "all":
            targets = [
                ("code", get_settings_target_path("code"), "settings file"),
                ("code-insiders", get_settings_target_path("code-insiders"), "settings file"),
                ("opencode", get_settings_target_path("opencode"), "opencode file"),
                ("pi", get_settings_target_path("pi"), "pi models file"),
                ("codex", get_settings_target_path("codex"), "codex config file"),
            ]

            applied = 0
            skipped = 0

            copilot_config = None
            opencode_generated = None
            pi_generated = None
            codex_generated = None

            for target, path_obj, label in targets:
                path = Path(path_obj).expanduser()
                if not path.exists():
                    print(f"Skipping {target}: file not found at {path}")
                    skipped += 1
                    continue

                print(f"Using {label}: {path}")

                if target in ("code", "code-insiders"):
                    if copilot_config is None:
                        copilot_config = generate_copilot_config(
                            api_base,
                            openai_url,
                            min_context=min_context,
                            tools_filter=tools_filter,
                            vision_filter=vision_filter,
                        )
                    update_settings_file(str(path), copilot_config)
                elif target == "opencode":
                    if opencode_generated is None:
                        opencode_generated = generate_opencode_provider(
                            api_base,
                            base_url,
                            min_context=min_context,
                            tools_filter=tools_filter,
                            vision_filter=vision_filter,
                        )
                    provider_id, provider = opencode_generated
                    update_opencode_file(str(path), provider_id, provider)
                elif target == "pi":
                    if pi_generated is None:
                        pi_generated = generate_pi_provider(
                            api_base,
                            base_url,
                            min_context=min_context,
                            tools_filter=tools_filter,
                            vision_filter=vision_filter,
                        )
                    provider_id, provider = pi_generated
                    update_pi_file(str(path), provider_id, provider)
                else:
                    if codex_generated is None:
                        codex_generated = generate_codex_config(
                            api_base,
                            base_url,
                            min_context=min_context,
                            tools_filter=tools_filter,
                            vision_filter=vision_filter,
                        )
                    update_codex_file(str(path), codex_generated)

                applied += 1

            if applied == 0:
                print("No installed harness config files found. Nothing to update.")
            else:
                print(f"Finished: updated {applied} target(s), skipped {skipped}.")
        elif output_format == "vscode":
            config = generate_copilot_config(
                api_base,
                openai_url,
                min_context=min_context,
                tools_filter=tools_filter,
                vision_filter=vision_filter,
            )

            if final_settings_path:
                # Update the settings file directly
                update_settings_file(final_settings_path, config)
            else:
                # Print the configuration to stdout
                output = {"github.copilot.chat.customOAIModels": config}
                print(json.dumps(output, indent=2))
        elif output_format == "opencode":
            provider_id, provider = generate_opencode_provider(
                api_base,
                base_url,
                min_context=min_context,
                tools_filter=tools_filter,
                vision_filter=vision_filter,
            )
            output = {
                "$schema": "https://opencode.ai/config.json",
                "provider": {
                    provider_id: provider,
                },
            }

            if final_settings_path:
                update_opencode_file(final_settings_path, provider_id, provider)
            else:
                print(json.dumps(output, indent=2))
        elif output_format == "pi":
            provider_id, provider = generate_pi_provider(
                api_base,
                base_url,
                min_context=min_context,
                tools_filter=tools_filter,
                vision_filter=vision_filter,
            )
            output = {
                "providers": {
                    provider_id: provider,
                },
            }

            if final_settings_path:
                update_pi_file(final_settings_path, provider_id, provider)
            else:
                print(json.dumps(output, indent=2))
        else:
            output = generate_codex_config(
                api_base,
                base_url,
                min_context=min_context,
                tools_filter=tools_filter,
                vision_filter=vision_filter,
            )

            if final_settings_path:
                update_codex_file(final_settings_path, output)
            else:
                print(tomli_w.dumps(output), end="")
            
    except requests.exceptions.ConnectionError as e:
        target = api_base
        click.echo(f"\nError: Could not connect to LM Studio at {target}", err=True)
        click.echo("\nPlease ensure:", err=True)
        click.echo("  1. LM Studio is running", err=True)
        click.echo("  2. Local server is started in LM Studio", err=True)
        click.echo("  3. Server is listening on the host/port from --base-url", err=True)
        click.echo("\nIf LM Studio is running on a different host/port, use:", err=True)
        click.echo("  --base-url http://HOST:PORT/v1", err=True)
        exit(1)
    except requests.exceptions.RequestException as e:
        target = api_base
        click.echo(f"\nError connecting to LM Studio API at {target}: {e}", err=True)
        exit(1)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        exit(1)


if __name__ == "__main__":
    main()
