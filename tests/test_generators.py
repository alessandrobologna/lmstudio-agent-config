import unittest

from lmstudio_agent_config.generators import (
    codex_profile_name_for_model,
    generate_codex_config,
    generate_codex_profiles,
    generate_copilot_config,
    generate_opencode_provider,
    generate_pi_provider,
)


MODEL_FIXTURES = [
    {
        "key": "Alpha Model",
        "type": "llm",
        "max_context_length": 8192,
        "capabilities": {"trained_for_tool_use": True, "vision": False},
    },
    {
        "key": "Vision/Model",
        "type": "llm",
        "max_context_length": 4096,
        "capabilities": {"trained_for_tool_use": False, "vision": True},
    },
    {
        "key": "embedder",
        "type": "embedding",
        "max_context_length": 1024,
    },
]


def _fetch_models(_api_base: str):
    return MODEL_FIXTURES


class TestGenerators(unittest.TestCase):
    def test_codex_profile_name_for_model_uniqueness(self):
        used = set()
        first = codex_profile_name_for_model("My Model", used)
        second = codex_profile_name_for_model("My Model", used)
        self.assertEqual(first, "lmstudio-my-model")
        self.assertEqual(second, "lmstudio-my-model-2")

    def test_generate_codex_profiles(self):
        profiles = generate_codex_profiles(["B", "A"], "provider")
        self.assertEqual(set(profiles.keys()), {"lmstudio-a", "lmstudio-b"})
        self.assertEqual(profiles["lmstudio-a"]["model_provider"], "provider")

    def test_generate_copilot_config(self):
        config = generate_copilot_config(
            "http://example/api",
            "http://example/v1",
            fetch_models_fn=_fetch_models,
        )
        self.assertEqual(list(config.keys()), ["Alpha Model", "Vision/Model"])
        field_order = list(config["Alpha Model"].keys())
        self.assertEqual(field_order, sorted(field_order))
        self.assertTrue(config["Alpha Model"]["toolCalling"])

    def test_generate_opencode_provider_modalities(self):
        provider_id, provider = generate_opencode_provider(
            "http://example/api",
            "http://example",
            fetch_models_fn=_fetch_models,
        )
        self.assertEqual(provider_id, "lmstudio")
        self.assertEqual(
            provider["models"]["Vision/Model"]["modalities"]["input"], ["text", "image"]
        )
        self.assertEqual(
            provider["models"]["Alpha Model"]["modalities"]["input"], ["text"]
        )

    def test_generate_pi_provider(self):
        provider_id, provider = generate_pi_provider(
            "http://example/api",
            "http://example",
            fetch_models_fn=_fetch_models,
        )
        self.assertEqual(provider_id, "lmstudio")
        self.assertTrue(provider["baseUrl"].endswith("/v1"))
        ids = [model["id"] for model in provider["models"]]
        self.assertEqual(ids, sorted(ids))

    def test_generate_codex_config(self):
        config = generate_codex_config(
            "http://example/api",
            "http://example",
            fetch_models_fn=_fetch_models,
        )
        self.assertIn("model_providers", config)
        self.assertIn("profiles", config)
        profiles = config["profiles"]
        self.assertTrue(
            any(profile.get("model") == "Alpha Model" for profile in profiles.values())
        )


if __name__ == "__main__":
    unittest.main()
