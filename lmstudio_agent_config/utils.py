import difflib
from typing import Callable


def detect_indentation(content: str) -> int:
    """Detect the indentation style from existing content."""
    for line in content.splitlines():
        if line and (line[0] == " " or line[0] == "\t"):
            # Found an indented line, extract the leading whitespace
            indent = ""
            for char in line:
                if char in (" ", "\t"):
                    indent += char
                else:
                    break
            if indent:
                return len(indent)
    # Default to 2 spaces if we can't detect
    return 2


def normalize_openai_base_url(url: str) -> str:
    """Ensure base URL ends with /v1 for OpenAI-compatible endpoints."""
    base = url.rstrip("/")
    if base.endswith("/v1"):
        return base
    return f"{base}/v1"


def show_diff_and_confirm(
    old_content: str,
    new_content: str,
    file_path: str,
    input_fn: Callable[[str], str] = input,
    print_fn: Callable[..., None] = print,
) -> str:
    """Show diff between old and new content and ask for confirmation.

    Returns: 'unchanged', 'apply', or 'cancel'.
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    # Use ndiff but only keep changed lines (+/-), mirroring the Rust behavior.
    diff = list(difflib.ndiff(old_lines, new_lines))
    changes = [line for line in diff if line and line[0] in ("+", "-")]

    if not changes:
        print_fn("No changes detected.")
        return "unchanged"

    print_fn(f"\nDiff preview for: {file_path}\n")
    for line in changes:
        if line[0] == "+":
            # Green for additions
            print_fn(f"\033[32m{line}\033[0m", end="")
        elif line[0] == "-":
            # Red for deletions
            print_fn(f"\033[31m{line}\033[0m", end="")
    print_fn("")

    # Ask for confirmation
    response = input_fn("\nApply these changes? [y/N]: ").strip().lower()
    if response in ["y", "yes"]:
        return "apply"
    return "cancel"
