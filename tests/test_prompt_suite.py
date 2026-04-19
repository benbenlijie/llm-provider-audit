from pathlib import Path
import unittest

from model_checker.config import load_prompt_suite


REPO_ROOT = Path(__file__).resolve().parents[1]


class PromptSuiteTests(unittest.TestCase):
    def test_default_prompt_suite(self) -> None:
        suite = load_prompt_suite(
            REPO_ROOT / "configs/prompt-suites/default.yaml"
        )
        self.assertEqual(suite.name, "default")
        self.assertGreaterEqual(len(suite.cases), 6)
        self.assertTrue(any(case.category == "strict_json" for case in suite.cases))
        self.assertTrue(all(case.tags == [] for case in suite.cases))

    def test_deep_prompt_suite_loads_case_metadata(self) -> None:
        suite = load_prompt_suite(
            REPO_ROOT / "configs/prompt-suites/differential/deep-v1.yaml"
        )
        self.assertEqual(suite.name, "differential-deep-v1")
        self.assertGreaterEqual(len(suite.cases), 12)

        case = next(item for item in suite.cases if item.case_id == "audit_brief_bullets")
        self.assertEqual(case.discriminator_type, "compressed-structure")
        self.assertIn("audit", case.tags)
        self.assertIn("structure", case.tags)
        self.assertEqual(case.turns, [])

        future_case = next(item for item in suite.cases if item.case_id == "future_multiturn_placeholder")
        self.assertEqual(len(future_case.turns), 2)
        self.assertEqual(future_case.turns[0]["role"], "user")
        self.assertEqual(future_case.turns[1]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
