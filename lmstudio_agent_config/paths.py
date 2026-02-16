import os
import platform
from pathlib import Path


def get_vscode_settings_path(editor_type: str) -> Path:
    """Get the settings.json path for VS Code or VS Code Insiders based on OS."""
    system = platform.system()
    home = Path.home()

    if editor_type == "code":
        if system == "Darwin":  # macOS
            return home / "Library/Application Support/Code/User/settings.json"
        if system == "Windows":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Code/User/settings.json"
        # Linux and others
        return home / ".config/Code/User/settings.json"
    if editor_type == "code-insiders":
        if system == "Darwin":  # macOS
            return (
                home / "Library/Application Support/Code - Insiders/User/settings.json"
            )
        if system == "Windows":
            appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
            return appdata / "Code - Insiders/User/settings.json"
        # Linux and others
        return home / ".config/Code - Insiders/User/settings.json"
    raise ValueError(f"Unknown editor type: {editor_type}")


def get_opencode_settings_path() -> Path:
    """Get the default opencode.json path."""
    home = Path.home()
    return home / ".opencode" / "opencode.json"


def get_pi_models_path() -> Path:
    """Get the default Pi models.json path."""
    home = Path.home()
    return home / ".pi" / "agent" / "models.json"


def get_codex_config_path() -> Path:
    """Get the default Codex config.toml path."""
    home = Path.home()
    return home / ".codex" / "config.toml"


def get_settings_target_path(setting: str) -> Path:
    """Resolve default path for a known settings target."""
    if setting == "opencode":
        return get_opencode_settings_path()
    if setting == "pi":
        return get_pi_models_path()
    if setting == "codex":
        return get_codex_config_path()
    return get_vscode_settings_path(setting)
