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

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

import click
import requests
import tomli_w
from click_help_colors import HelpColorsCommand

from lmstudio_agent_config.files import (
    update_codex_file,
    update_opencode_file,
    update_pi_file,
    update_settings_file,
)
from lmstudio_agent_config.generators import (
    generate_codex_config,
    generate_copilot_config,
    generate_opencode_provider,
    generate_pi_provider,
)
from lmstudio_agent_config.paths import get_settings_target_path
from lmstudio_agent_config.render import render_models_table


@click.command(
    context_settings={"help_option_names": ["-h", "--help"]},
    cls=HelpColorsCommand,
    help_headers_color="yellow",
    help_options_color="green",
)
@click.option(
    "--base-url",
    metavar="BASE_URL",
    default="http://localhost:1234/v1",
    show_default=True,
    help="Base URL to write in config (where the client will connect)",
)
@click.option(
    "--min-context",
    metavar="TOKENS",
    type=click.IntRange(min=0),
    default=None,
    help="Only include models with max_context_length >= TOKENS",
)
@click.option(
    "--tools",
    "tools_required",
    is_flag=True,
    help="Only include models that support tool use",
)
@click.option(
    "--no-tools",
    "tools_excluded",
    is_flag=True,
    help="Only include models that do not support tool use",
)
@click.option(
    "--vision",
    "vision_required",
    is_flag=True,
    help="Only include models that support vision",
)
@click.option(
    "--no-vision",
    "vision_excluded",
    is_flag=True,
    help="Only include models that do not support vision",
)
@click.option(
    "--settings",
    metavar="SETTINGS",
    type=click.Choice(
        ["code", "code-insiders", "opencode", "pi", "codex", "all"],
        case_sensitive=False,
    ),
    help="Auto-detect settings path (code, code-insiders, opencode, pi, codex, all)",
)
@click.option(
    "--settings-path",
    metavar="SETTINGS_PATH",
    type=click.Path(),
    help=(
        "Path to settings file (overrides --settings auto-detect; prints a model list if "
        "neither --settings nor --settings-path is provided)"
    ),
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

    tools_filter = (
        "required" if tools_required else "exclude" if tools_excluded else "any"
    )
    vision_filter = (
        "required" if vision_required else "exclude" if vision_excluded else "any"
    )

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
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
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
                (
                    "code-insiders",
                    get_settings_target_path("code-insiders"),
                    "settings file",
                ),
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

    except requests.exceptions.ConnectionError:
        target = api_base
        click.echo(f"\nError: Could not connect to LM Studio at {target}", err=True)
        click.echo("\nPlease ensure:", err=True)
        click.echo("  1. LM Studio is running", err=True)
        click.echo("  2. Local server is started in LM Studio", err=True)
        click.echo(
            "  3. Server is listening on the host/port from --base-url", err=True
        )
        click.echo("\nIf LM Studio is running on a different host/port, use:", err=True)
        click.echo("  --base-url http://HOST:PORT/v1", err=True)
        raise SystemExit(1)
    except requests.exceptions.RequestException as e:
        target = api_base
        click.echo(f"\nError connecting to LM Studio API at {target}: {e}", err=True)
        raise SystemExit(1)
    except Exception as e:
        click.echo(f"\nError: {e}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
