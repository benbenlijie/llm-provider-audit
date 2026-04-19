import unittest

from model_checker.sampling.normalizer import evaluate_expectations, text_passes_expectations


class NormalizerExpectationTests(unittest.TestCase):
    def test_evaluate_expectations_supports_structure_constraints(self) -> None:
        text = "- baseline drift\n- compare outputs\n- watch failures"
        checks = evaluate_expectations(
            text,
            {
                "must_include_substrings": ["baseline", "failures"],
                "must_exclude_substrings": ["policy"],
                "exact_bullet_count": 3,
                "max_sentences": 3,
            },
        )
        self.assertEqual(
            checks,
            {
                "must_include_substrings": True,
                "must_exclude_substrings": True,
                "max_sentences": True,
                "exact_bullet_count": True,
            },
        )

    def test_text_passes_expectations_combines_all_supported_checks(self) -> None:
        text = '{"evidence":"match","limitation":"small sample","next_step":"rerun"}'
        passed = text_passes_expectations(
            text,
            {
                "json_keys": ["evidence", "limitation", "next_step"],
                "must_include_substrings": ["match"],
                "must_exclude_substrings": ["markdown"],
                "max_sentences": 1,
            },
        )
        self.assertTrue(passed)

    def test_text_passes_expectations_returns_none_when_no_supported_keys_exist(self) -> None:
        self.assertIsNone(text_passes_expectations("hello", {"exact_output": "hello"}))


if __name__ == "__main__":
    unittest.main()
