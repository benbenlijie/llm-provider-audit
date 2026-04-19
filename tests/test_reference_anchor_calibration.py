import unittest

from model_checker.analysis.reference_anchor_calibration import summarize_reference_anchor_calibration
from model_checker.domain import AnchorCalibrationConfig, FingerprintConfig, PromptCase, PromptSuite, SampleResult


def build_sample(provider: str, case_id: str, text: str) -> SampleResult:
    return SampleResult(
        provider=provider,
        case_id=case_id,
        attempt=1,
        success=True,
        text=text,
        normalized_text=text.lower(),
        latency_ms=1.0,
        error=None,
        raw_response={},
    )


class ReferenceAnchorCalibrationTests(unittest.TestCase):
    def test_summarize_reference_anchor_calibration_returns_thresholds(self) -> None:
        suite = PromptSuite(
            name="anchor-suite",
            cases=[
                PromptCase(case_id="exact_alpha", category="exact", prompt=""),
                PromptCase(case_id="reasoning_note", category="reasoning", prompt=""),
            ],
        )
        calibration = summarize_reference_anchor_calibration(
            suite,
            "official",
            batch_samples=[
                [
                    build_sample("official", "exact_alpha", "alpha-17"),
                    build_sample("official", "reasoning_note", "reference baseline note"),
                ],
                [
                    build_sample("official", "exact_alpha", "alpha-17"),
                    build_sample("official", "reasoning_note", "reference concise note"),
                ],
                [
                    build_sample("official", "exact_alpha", "alpha-17"),
                    build_sample("official", "reasoning_note", "reference baseline note"),
                ],
            ],
            category_weights={"exact": 1.5, "reasoning": 0.75},
            fingerprinting=FingerprintConfig(
                enabled=True,
                open_set_min_anchor_similarity=0.4,
                min_reference_margin=0.05,
                reference_margin_scale=0.2,
            ),
            anchor_calibration=AnchorCalibrationConfig(
                enabled=True,
                batch_count=3,
                batch_repetitions=2,
                inter_batch_cooldown_ms=0,
                similarity_quantile=0.1,
                threshold_margin=0.02,
            ),
        )
        self.assertTrue(calibration["available"])
        self.assertEqual(calibration["batch_count"], 3)
        self.assertEqual(len(calibration["pairwise_batch_similarities"]), 3)
        self.assertLessEqual(
            calibration["open_set_threshold_to_apply"],
            calibration["configured_open_set_threshold"],
        )
        self.assertGreater(calibration["pairwise_similarity_quantile"], 0.0)


if __name__ == "__main__":
    unittest.main()
