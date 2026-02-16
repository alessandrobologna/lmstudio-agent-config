import re
from collections import OrderedDict
from typing import Callable

from lmstudio_agent_config.models import (
    fetch_models,
    filter_models,
    get_model_id,
    model_supports_tool_calling,
    model_supports_vision,
)
from lmstudio_agent_config.utils import normalize_openai_base_url


def codex_profile_name_for_model(
    model_id: str, used_names: set[str], prefix: str = "lmstudio"
) -> str:
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


def generate_codex_profiles(model_ids: list[str], provider_id: str) -> dict[str, dict]:
    """Generate one Codex profile per LM Studio model."""
    used_names: set[str] = set()
    profiles: dict[str, dict] = {}
    for model_id in sorted(set(model_ids)):
        profile_name = codex_profile_name_for_model(model_id, used_names)
        profiles[profile_name] = {
            "model": model_id,
            "model_provider": provider_id,
        }
    return profiles


def generate_copilot_config(
    api_base: str,
    openai_url: str,
    min_context: int | None = None,
    tools_filter: str = "any",
    vision_filter: str = "any",
    fetch_models_fn: Callable[[str], list[dict]] = fetch_models,
) -> dict[str, dict]:
    models = filter_models(
        fetch_models_fn(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    config: dict[str, dict] = {}
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
    api_base: str,
    base_url: str,
    provider_id: str = "lmstudio",
    provider_name: str = "LM Studio (local)",
    min_context: int | None = None,
    tools_filter: str = "any",
    vision_filter: str = "any",
    fetch_models_fn: Callable[[str], list[dict]] = fetch_models,
) -> tuple[str, dict]:
    models = filter_models(
        fetch_models_fn(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    config: dict[str, dict] = {}
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
            config[model_id]["modalities"] = {
                "input": ["text", "image"],
                "output": ["text"],
            }
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
    api_base: str,
    base_url: str,
    provider_id: str = "lmstudio",
    min_context: int | None = None,
    tools_filter: str = "any",
    vision_filter: str = "any",
    fetch_models_fn: Callable[[str], list[dict]] = fetch_models,
) -> tuple[str, dict]:
    models = filter_models(
        fetch_models_fn(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    config: list[dict] = []
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
    api_base: str,
    base_url: str,
    provider_id: str = "lmstudio_local",
    provider_name: str = "LM Studio (local)",
    min_context: int | None = None,
    tools_filter: str = "any",
    vision_filter: str = "any",
    fetch_models_fn: Callable[[str], list[dict]] = fetch_models,
) -> dict[str, dict]:
    models = filter_models(
        fetch_models_fn(api_base),
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    llm_ids: list[str] = []
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
