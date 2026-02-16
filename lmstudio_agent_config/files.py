import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import json5
import tomli_w

from lmstudio_agent_config.utils import detect_indentation, show_diff_and_confirm

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib


def _ensure_parent(path: Path) -> None:
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _create_backup(path: Path, fallback_stem: str, extension: str) -> Path:
    date_tag = datetime.now().strftime("%y%m%d")
    stem = path.stem or fallback_stem

    index = 0
    while True:
        backup_name = f"{stem}.{date_tag}-{index}.backup.{extension}"
        backup_path = path.with_name(backup_name)
        if not backup_path.exists():
            break
        index += 1

    shutil.copy2(path, backup_path)
    return backup_path


def update_opencode_file(
    opencode_path: str,
    provider_id: str,
    provider: dict,
    confirm_fn: Callable[[str, str, str], str] = show_diff_and_confirm,
) -> None:
    """Update opencode.json with the generated provider configuration."""
    opencode_file = Path(opencode_path).expanduser()

    # Read existing content
    old_content = ""
    if opencode_file.exists():
        try:
            with open(opencode_file, "r", encoding="utf-8") as f:
                old_content = f.read()
            opencode_config = json5.loads(old_content)
        except Exception as e:
            print(
                f"Warning: Could not parse existing opencode config ({e}), creating new structure..."
            )
            opencode_config = {}
    else:
        opencode_config = {}

    # Detect original indentation
    indent = detect_indentation(old_content) if old_content else 2

    if not isinstance(opencode_config, dict):
        print(
            "Warning: opencode config is not a JSON object, overwriting with new structure..."
        )
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

    decision = confirm_fn(old_content, new_content, str(opencode_file))
    if decision == "unchanged":
        return
    if decision == "cancel":
        print("Operation cancelled by user")
        sys.exit(0)

    _ensure_parent(opencode_file)

    if opencode_file.exists():
        backup_path = _create_backup(opencode_file, "opencode", "json")
        print(f"Created backup at {backup_path}")

    with open(opencode_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(
        f"Successfully updated {opencode_file} with {len(provider.get('models', {}))} models"
    )


def update_pi_file(
    pi_path: str,
    provider_id: str,
    provider: dict,
    confirm_fn: Callable[[str, str, str], str] = show_diff_and_confirm,
) -> None:
    """Update Pi models.json with the generated provider configuration."""
    pi_file = Path(pi_path).expanduser()

    old_content = ""
    if pi_file.exists():
        try:
            with open(pi_file, "r", encoding="utf-8") as f:
                old_content = f.read()
            pi_config = json5.loads(old_content)
        except Exception as e:
            print(
                f"Warning: Could not parse existing Pi config ({e}), creating new structure..."
            )
            pi_config = {}
    else:
        pi_config = {}

    indent = detect_indentation(old_content) if old_content else 2

    if not isinstance(pi_config, dict):
        print(
            "Warning: Pi config is not a JSON object, overwriting with new structure..."
        )
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

    decision = confirm_fn(old_content, new_content, str(pi_file))
    if decision == "unchanged":
        return
    if decision == "cancel":
        print("Operation cancelled by user")
        sys.exit(0)

    _ensure_parent(pi_file)

    if pi_file.exists():
        backup_path = _create_backup(pi_file, "models", "json")
        print(f"Created backup at {backup_path}")

    with open(pi_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(
        f"Successfully updated {pi_file} with {len(provider.get('models', []))} models"
    )


def update_codex_file(
    codex_path: str,
    codex_config: dict,
    confirm_fn: Callable[[str, str, str], str] = show_diff_and_confirm,
) -> None:
    """Update Codex config.toml with the generated provider configuration."""
    codex_file = Path(codex_path).expanduser()

    old_content = ""
    if codex_file.exists():
        try:
            with open(codex_file, "r", encoding="utf-8") as f:
                old_content = f.read()
            parsed = tomllib.loads(old_content)
        except Exception as e:
            print(
                f"Warning: Could not parse existing Codex config ({e}), creating new structure..."
            )
            parsed = {}
    else:
        parsed = {}

    if not isinstance(parsed, dict):
        print(
            "Warning: Codex config is not a TOML object, overwriting with new structure..."
        )
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

    decision = confirm_fn(old_content, new_content, str(codex_file))
    if decision == "unchanged":
        return
    if decision == "cancel":
        print("Operation cancelled by user")
        sys.exit(0)

    _ensure_parent(codex_file)

    if codex_file.exists():
        backup_path = _create_backup(codex_file, "config", "toml")
        print(f"Created backup at {backup_path}")

    with open(codex_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    provider_ids = ", ".join(sorted(providers_update.keys()))
    print(
        f"Successfully updated {codex_file} with provider(s) '{provider_ids}' "
        f"and {len(profiles_update)} profiles"
    )


def update_settings_file(
    settings_path: str,
    config: dict,
    confirm_fn: Callable[[str, str, str], str] = show_diff_and_confirm,
) -> None:
    """Update the settings.json file with the new model configuration."""
    settings_file = Path(settings_path).expanduser()

    # Read existing content
    old_content = ""
    if settings_file.exists():
        try:
            # Use json5 to parse JSONC files (handles comments and trailing commas)
            with open(settings_file, "r", encoding="utf-8") as f:
                old_content = f.read()

            settings = json5.loads(old_content)

        except Exception as e:
            # If parsing fails, create a minimal settings structure
            print(
                f"Warning: Could not parse existing settings ({e}), creating new structure..."
            )
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
    decision = confirm_fn(old_content, new_content, str(settings_file))
    if decision == "unchanged":
        # Nothing to do, leave file and backups untouched.
        return
    if decision == "cancel":
        print("Operation cancelled by user")
        sys.exit(0)

    # Create dated backup before modifying, e.g. settings.250924-0.backup.json
    if settings_file.exists():
        backup_path = _create_backup(settings_file, "settings", "json")
        print(f"Created backup at {backup_path}")

    # Write back to file (as regular JSON with proper formatting)
    _ensure_parent(settings_file)
    with open(settings_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"Successfully updated {settings_file} with {len(config)} models")
