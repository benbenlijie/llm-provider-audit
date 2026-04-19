import unittest

from model_checker.analysis.verdict import determine_verdict
from model_checker.domain import CalibrationConfig, ScoringConfig


class VerdictTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scoring = ScoringConfig(
            likely_match_similarity_ratio=0.9,
            suspicious_similarity_ratio=0.75,
            max_failure_rate=0.3,
            max_json_pass_delta=0.34,
            min_weighted_tail_probability=0.35,
            severe_weighted_tail_probability=0.12,
            outlier_case_pvalue_threshold=0.1,
            max_outlier_case_count=2,
            min_negative_control_margin=0.05,
        )
        self.calibration = CalibrationConfig(
            min_reference_samples=2,
            min_calibrated_cases=4,
            category_weights={},
        )

    def test_likely_match(self) -> None:
        verdict = determine_verdict(
            {
                "cross_similarity_ratio": 0.95,
                "weighted_relative_similarity": 0.95,
                "weighted_tail_probability": 0.8,
                "outlier_case_count": 0,
                "mean_failure_rate": 0.0,
                "mean_json_pass_delta": 0.1,
                "calibrated_case_count": 5,
            },
            self.scoring,
            self.calibration,
        )
        self.assertEqual(verdict["label"], "likely_match")

    def test_strong_mismatch(self) -> None:
        verdict = determine_verdict(
            {
                "cross_similarity_ratio": 0.52,
                "weighted_relative_similarity": 0.52,
                "weighted_tail_probability": 0.05,
                "outlier_case_count": 3,
                "mean_failure_rate": 0.0,
                "mean_json_pass_delta": 0.7,
                "calibrated_case_count": 5,
            },
            self.scoring,
            self.calibration,
        )
        self.assertEqual(verdict["label"], "strong_mismatch")

    def test_insufficient_evidence(self) -> None:
        verdict = determine_verdict(
            {
                "cross_similarity_ratio": 0.99,
                "weighted_relative_similarity": 0.99,
                "weighted_tail_probability": 0.9,
                "outlier_case_count": 0,
                "mean_failure_rate": 0.6,
                "mean_json_pass_delta": 0.0,
                "calibrated_case_count": 5,
            },
            self.scoring,
            self.calibration,
        )
        self.assertEqual(verdict["label"], "insufficient_evidence")

    def test_insufficient_when_calibration_cases_too_low(self) -> None:
        verdict = determine_verdict(
            {
                "cross_similarity_ratio": 0.99,
                "weighted_relative_similarity": 0.99,
                "weighted_tail_probability": 0.9,
                "outlier_case_count": 0,
                "mean_failure_rate": 0.0,
                "mean_json_pass_delta": 0.0,
                "calibrated_case_count": 1,
            },
            self.scoring,
            self.calibration,
        )
        self.assertEqual(verdict["label"], "insufficient_evidence")
        self.assertEqual(verdict["reasons"], ["reference calibration evidence is insufficient"])

    def test_low_calibration_and_high_failure_include_both_reasons(self) -> None:
        verdict = determine_verdict(
            {
                "cross_similarity_ratio": 0.0,
                "weighted_relative_similarity": 0.0,
                "weighted_tail_probability": 0.0,
                "outlier_case_count": 0,
                "mean_failure_rate": 1.0,
                "mean_json_pass_delta": 0.0,
                "calibrated_case_count": 0,
            },
            self.scoring,
            self.calibration,
        )
        self.assertEqual(verdict["label"], "insufficient_evidence")
        self.assertEqual(
            verdict["reasons"],
            [
                "reference calibration evidence is insufficient",
                "target provider failure rate is too high",
            ],
        )

    def test_negative_control_can_downgrade_likely_match(self) -> None:
        verdict = determine_verdict(
            {
                "cross_similarity_ratio": 0.97,
                "weighted_relative_similarity": 0.97,
                "weighted_tail_probability": 0.8,
                "outlier_case_count": 0,
                "mean_failure_rate": 0.0,
                "mean_json_pass_delta": 0.0,
                "calibrated_case_count": 6,
            },
            self.scoring,
            self.calibration,
            negative_control_comparison={
                "available": True,
                "best_negative_provider": "official_gpt52",
                "relative_margin_vs_best_negative": 0.01,
            },
        )
        self.assertEqual(verdict["label"], "suspicious_mismatch")


if __name__ == "__main__":
    unittest.main()
