import unittest

from lmstudio_agent_config.utils import (
    detect_indentation,
    normalize_openai_base_url,
    show_diff_and_confirm,
)


class TestUtils(unittest.TestCase):
    def test_detect_indentation_spaces(self):
        content = '{\n  "a": 1\n}'
        self.assertEqual(detect_indentation(content), 2)

    def test_detect_indentation_tabs(self):
        content = '{\n\t"a": 1\n}'
        self.assertEqual(detect_indentation(content), 1)

    def test_detect_indentation_default(self):
        content = '{\n"a": 1\n}'
        self.assertEqual(detect_indentation(content), 2)

    def test_normalize_openai_base_url(self):
        self.assertEqual(
            normalize_openai_base_url("http://localhost:1234"),
            "http://localhost:1234/v1",
        )
        self.assertEqual(
            normalize_openai_base_url("http://localhost:1234/v1"),
            "http://localhost:1234/v1",
        )

    def test_show_diff_and_confirm_unchanged(self):
        result = show_diff_and_confirm(
            "same", "same", "file.txt", input_fn=lambda _: "n"
        )
        self.assertEqual(result, "unchanged")


if __name__ == "__main__":
    unittest.main()
