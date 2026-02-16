from rich.console import Console
from rich.text import Text

from lmstudio_agent_config.generators import generate_codex_profiles
from lmstudio_agent_config.models import (
    fetch_models,
    filter_models,
    get_model_id,
    model_supports_tool_calling,
    model_supports_vision,
)


def render_models_table(
    api_base: str,
    min_context: int | None = None,
    tools_filter: str = "any",
    vision_filter: str = "any",
) -> None:
    """Render discovered models as a rich, human-readable list."""
    all_models = fetch_models(api_base)
    models = filter_models(
        all_models,
        min_context=min_context,
        tools_filter=tools_filter,
        vision_filter=vision_filter,
    )
    rows: list[dict] = []
    llm_count = 0
    tools_count = 0
    vision_count = 0

    llm_ids: list[str] = []
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

    profile_by_model: dict[str, str] = {}
    for profile_name, profile in generate_codex_profiles(
        llm_ids, "lmstudio_local"
    ).items():
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
        details.append(
            row["context"], style="yellow" if row["context"] != "-" else "dim"
        )
        details.append(" | tools: ", style="dim")
        details.append(
            "yes" if row["tools_yes"] else "no",
            style="green" if row["tools_yes"] else "dim",
        )
        details.append(" | vision: ", style="dim")
        details.append(
            "yes" if row["vision_yes"] else "no",
            style="green" if row["vision_yes"] else "dim",
        )
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
    console.print(
        "[dim]Tip:[/] run [cyan]codex --profile <name>[/cyan] to switch LM Studio models."
    )
