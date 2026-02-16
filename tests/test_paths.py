import unittest
from pathlib import Path
from unittest.mock import patch

from lmstudio_agent_config.paths import (
    get_settings_target_path,
    get_vscode_settings_path,
)


class TestPaths(unittest.TestCase):
    def test_get_vscode_settings_path_linux(self):
        with (
            patch("lmstudio_agent_config.paths.platform.system", return_value="Linux"),
            patch(
                "lmstudio_agent_config.paths.Path.home", return_value=Path("/home/test")
            ),
        ):
            path = get_vscode_settings_path("code")
            self.assertEqual(path, Path("/home/test/.config/Code/User/settings.json"))

    def test_get_vscode_settings_path_windows(self):
        with (
            patch(
                "lmstudio_agent_config.paths.platform.system", return_value="Windows"
            ),
            patch(
                "lmstudio_agent_config.paths.Path.home",
                return_value=Path("C:/Users/Test"),
            ),
            patch.dict(
                "lmstudio_agent_config.paths.os.environ",
                {"APPDATA": "C:/Users/Test/AppData/Roaming"},
            ),
        ):
            path = get_vscode_settings_path("code")
            self.assertEqual(
                path, Path("C:/Users/Test/AppData/Roaming/Code/User/settings.json")
            )

    def test_get_settings_target_path_codex(self):
        with patch(
            "lmstudio_agent_config.paths.Path.home", return_value=Path("/home/test")
        ):
            path = get_settings_target_path("codex")
            self.assertEqual(path, Path("/home/test/.codex/config.toml"))

    def test_get_vscode_settings_path_unknown(self):
        with self.assertRaises(ValueError):
            get_vscode_settings_path("unknown")


if __name__ == "__main__":
    unittest.main()
