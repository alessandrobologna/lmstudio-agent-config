import unittest

from lmstudio_agent_config.models import (
    filter_models,
    model_matches_filters,
    model_supports_tool_calling,
    model_supports_vision,
)


MODEL_FIXTURES = [
    {
        "key": "alpha",
        "type": "llm",
        "max_context_length": 8192,
        "capabilities": {"trained_for_tool_use": True, "vision": False},
    },
    {
        "key": "beta",
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


class TestModels(unittest.TestCase):
    def test_model_supports_flags(self):
        self.assertTrue(model_supports_tool_calling(MODEL_FIXTURES[0]))
        self.assertFalse(model_supports_tool_calling(MODEL_FIXTURES[1]))
        self.assertFalse(model_supports_tool_calling(MODEL_FIXTURES[2]))

        self.assertFalse(model_supports_vision(MODEL_FIXTURES[0]))
        self.assertTrue(model_supports_vision(MODEL_FIXTURES[1]))
        self.assertFalse(model_supports_vision(MODEL_FIXTURES[2]))

    def test_model_matches_filters_min_context(self):
        self.assertTrue(model_matches_filters(MODEL_FIXTURES[0], min_context=4096))
        self.assertFalse(model_matches_filters(MODEL_FIXTURES[1], min_context=8192))

    def test_model_matches_filters_tools(self):
        self.assertTrue(
            model_matches_filters(MODEL_FIXTURES[0], tools_filter="required")
        )
        self.assertFalse(
            model_matches_filters(MODEL_FIXTURES[1], tools_filter="required")
        )
        self.assertFalse(
            model_matches_filters(MODEL_FIXTURES[2], tools_filter="required")
        )

    def test_model_matches_filters_vision(self):
        self.assertTrue(
            model_matches_filters(MODEL_FIXTURES[1], vision_filter="required")
        )
        self.assertFalse(
            model_matches_filters(MODEL_FIXTURES[0], vision_filter="required")
        )
        self.assertFalse(
            model_matches_filters(MODEL_FIXTURES[2], vision_filter="required")
        )

    def test_filter_models_combined(self):
        filtered = filter_models(
            MODEL_FIXTURES, min_context=3000, tools_filter="any", vision_filter="any"
        )
        self.assertEqual({model["key"] for model in filtered}, {"alpha", "beta"})

        filtered_tools = filter_models(MODEL_FIXTURES, tools_filter="required")
        self.assertEqual([model["key"] for model in filtered_tools], ["alpha"])


if __name__ == "__main__":
    unittest.main()
