import json
import tempfile
import unittest
from pathlib import Path

from lmstudio_agent_config.files import (
    update_codex_file,
    update_opencode_file,
    update_pi_file,
    update_settings_file,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


class TestFiles(unittest.TestCase):
    def _confirm_apply(self, _old, _new, _path):
        return "apply"

    def test_update_settings_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "settings.json"
            path.write_text('{\n  "editor.fontSize": 14\n}', encoding="utf-8")

            update_settings_file(
                str(path),
                {"model": {"name": "Test"}},
                confirm_fn=self._confirm_apply,
            )

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("github.copilot.chat.customOAIModels", data)

            backups = list(Path(tmpdir).glob("settings.*.backup.json"))
            self.assertTrue(backups)

    def test_update_opencode_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "opencode.json"
            path.write_text('{\n  "provider": {}\n}', encoding="utf-8")

            provider = {
                "npm": "@ai-sdk/openai-compatible",
                "name": "LM Studio (local)",
                "options": {"baseURL": "http://example/v1"},
                "models": {"alpha": {"name": "alpha"}},
            }
            update_opencode_file(
                str(path),
                "lmstudio",
                provider,
                confirm_fn=self._confirm_apply,
            )

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("provider", data)
            self.assertIn("lmstudio", data["provider"])

    def test_update_pi_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "models.json"
            path.write_text('{\n  "providers": {}\n}', encoding="utf-8")

            provider = {
                "baseUrl": "http://example/v1",
                "api": "openai-completions",
                "apiKey": "lm-studio",
                "models": [{"id": "alpha"}],
            }
            update_pi_file(
                str(path),
                "lmstudio",
                provider,
                confirm_fn=self._confirm_apply,
            )

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("providers", data)
            self.assertIn("lmstudio", data["providers"])

    def test_update_codex_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.toml"
            path.write_text("", encoding="utf-8")

            config = {
                "model_providers": {
                    "lmstudio_local": {
                        "name": "LM Studio",
                        "base_url": "http://example/v1",
                        "wire_api": "responses",
                    }
                },
                "profiles": {
                    "lmstudio-alpha": {
                        "model": "alpha",
                        "model_provider": "lmstudio_local",
                    }
                },
            }
            update_codex_file(
                str(path),
                config,
                confirm_fn=self._confirm_apply,
            )

            data = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertIn("model_providers", data)
            self.assertIn("profiles", data)


if __name__ == "__main__":
    unittest.main()
