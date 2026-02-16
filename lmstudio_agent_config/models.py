from typing import Callable
import requests


def fetch_models(api_base: str, http_get: Callable = requests.get) -> list[dict]:
    resp = http_get(api_base)
    resp.raise_for_status()
    payload = resp.json()

    if isinstance(payload.get("models"), list):
        return payload["models"]

    raise ValueError("Unexpected model list response format: expected 'models' array")


def get_model_id(model: dict) -> str | None:
    """Get model identifier from v1 (`key`) payloads."""
    return model.get("key")


def model_supports_tool_calling(model: dict) -> bool:
    """Detect tool calling from v1 capabilities object."""
    capabilities = model.get("capabilities")
    if isinstance(capabilities, dict):
        return bool(capabilities.get("trained_for_tool_use"))
    return False


def model_supports_vision(model: dict) -> bool:
    """Detect vision support from v1 capabilities object."""
    capabilities = model.get("capabilities")
    if isinstance(capabilities, dict):
        return bool(capabilities.get("vision"))
    return False


def model_matches_filters(
    model: dict,
    min_context: int | None = None,
    tools_filter: str = "any",
    vision_filter: str = "any",
) -> bool:
    """Check whether a model matches active filters."""
    if min_context is not None:
        max_context = model.get("max_context_length")
        if not isinstance(max_context, int) or max_context < min_context:
            return False

    has_tools = (
        model_supports_tool_calling(model) if model.get("type") == "llm" else False
    )
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


def filter_models(
    models: list[dict],
    min_context: int | None = None,
    tools_filter: str = "any",
    vision_filter: str = "any",
) -> list[dict]:
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
