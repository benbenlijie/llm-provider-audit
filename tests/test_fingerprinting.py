import unittest

from model_checker.analysis.fingerprinting import compare_provider_to_anchors
from model_checker.domain import CaseAnalysis, FingerprintConfig, PromptCase, PromptSuite, SampleResult
from model_checker.reporting import render_markdown_report
from model_checker.domain import AuditRun, ProviderSnapshot, TargetAnalysis


def build_sample(provider: str, case_id: str, text: str, *, success: bool = True) -> SampleResult:
    return SampleResult(
        provider=provider,
        case_id=case_id,
        attempt=1,
        success=success,
        text=text,
        normalized_text=text.lower(),
        latency_ms=1.0,
        error=None if success else "failed",
        raw_response={},
    )


class FingerprintingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = PromptSuite(
            name="fingerprint-test",
            cases=[
                PromptCase(case_id="exact_alpha", category="exact", prompt=""),
                PromptCase(case_id="reasoning_note", category="reasoning", prompt=""),
            ],
        )
        self.weights = {"exact": 1.5, "reasoning": 0.75}
        self.fingerprinting = FingerprintConfig(
            enabled=True,
            open_set_min_anchor_similarity=0.4,
            min_reference_margin=0.05,
            reference_margin_scale=0.2,
        )

    def test_reference_nearest_neighbor(self) -> None:
        samples = [
            build_sample("official", "exact_alpha", "alpha-17"),
            build_sample("official", "reasoning_note", "reference baseline note"),
            build_sample("official_gpt52", "exact_alpha", "beta-22"),
            build_sample("official_gpt52", "reasoning_note", "lower tier wording"),
            build_sample("proxy", "exact_alpha", "alpha-17"),
            build_sample("proxy", "reasoning_note", "reference baseline note"),
        ]
        result = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52"],
            category_weights=self.weights,
            fingerprinting=self.fingerprinting,
            max_anchor_failure_rate=0.3,
        )
        self.assertTrue(result["available"])
        self.assertEqual(result["label"], "reference_nearest_neighbor")
        self.assertEqual(result["nearest_anchor_provider"], "official")
        self.assertGreater(result["reference_margin_vs_best_alternative"], 0.05)
        self.assertGreaterEqual(result["calibrated_reference_margin_threshold"], 0.05)

    def test_open_set_suspicious_when_all_anchors_are_far(self) -> None:
        samples = [
            build_sample("official", "exact_alpha", "alpha-17"),
            build_sample("official", "reasoning_note", "reference baseline note"),
            build_sample("official_gpt52", "exact_alpha", "beta-22"),
            build_sample("official_gpt52", "reasoning_note", "lower tier wording"),
            build_sample("proxy", "exact_alpha", "zzzzzz"),
            build_sample("proxy", "reasoning_note", "qqqqqq"),
        ]
        result = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52"],
            category_weights=self.weights,
            fingerprinting=self.fingerprinting,
            max_anchor_failure_rate=0.3,
        )
        self.assertEqual(result["label"], "open_set_suspicious")
        self.assertTrue(result["open_set_suspicious"])
        self.assertEqual(result["open_set_threshold_source"], "config")

    def test_reference_anchor_calibration_can_relax_open_set_threshold(self) -> None:
        fingerprinting = FingerprintConfig(
            enabled=True,
            open_set_min_anchor_similarity=1.1,
            min_reference_margin=0.05,
            reference_margin_scale=0.2,
        )
        samples = [
            build_sample("official", "exact_alpha", "alpha-17"),
            build_sample("official", "reasoning_note", "reference baseline note"),
            build_sample("official_gpt52", "exact_alpha", "beta-22"),
            build_sample("official_gpt52", "reasoning_note", "lower tier wording"),
            build_sample("proxy", "exact_alpha", "alpha-17"),
            build_sample("proxy", "reasoning_note", "reference baseline note"),
        ]
        without_calibration = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52"],
            category_weights=self.weights,
            fingerprinting=fingerprinting,
            max_anchor_failure_rate=0.3,
        )
        with_calibration = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52"],
            category_weights=self.weights,
            fingerprinting=fingerprinting,
            max_anchor_failure_rate=0.3,
            reference_anchor_calibration={"available": True, "open_set_threshold_to_apply": 0.9},
        )
        self.assertEqual(without_calibration["label"], "open_set_suspicious")
        self.assertEqual(with_calibration["label"], "reference_nearest_neighbor")
        self.assertEqual(with_calibration["open_set_threshold_source"], "reference_anchor_calibration")
        self.assertEqual(with_calibration["open_set_similarity_threshold_used"], 0.9)

    def test_closest_non_reference_anchor(self) -> None:
        samples = [
            build_sample("official", "exact_alpha", "alpha-17"),
            build_sample("official", "reasoning_note", "reference baseline note"),
            build_sample("official_gpt52", "exact_alpha", "beta-22"),
            build_sample("official_gpt52", "reasoning_note", "lower tier wording"),
            build_sample("proxy", "exact_alpha", "beta-22"),
            build_sample("proxy", "reasoning_note", "lower tier wording"),
        ]
        result = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52"],
            category_weights=self.weights,
            fingerprinting=self.fingerprinting,
            max_anchor_failure_rate=0.3,
        )
        self.assertEqual(result["label"], "closest_non_reference_anchor")
        self.assertEqual(result["nearest_anchor_provider"], "official_gpt52")

    def test_calibrated_margin_threshold_can_make_match_ambiguous(self) -> None:
        fingerprinting = FingerprintConfig(
            enabled=True,
            open_set_min_anchor_similarity=0.4,
            min_reference_margin=0.05,
            reference_margin_scale=1.0,
        )
        samples = [
            build_sample("official", "exact_alpha", "alpha-17"),
            build_sample("official", "reasoning_note", "reference official wording"),
            build_sample("official_gpt52", "exact_alpha", "beta-22"),
            build_sample("official_gpt52", "reasoning_note", "older concise wording"),
            build_sample("proxy", "exact_alpha", "alpha-17"),
            build_sample("proxy", "reasoning_note", "reference concise wording"),
        ]
        result = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52"],
            category_weights=self.weights,
            fingerprinting=fingerprinting,
            max_anchor_failure_rate=0.3,
        )
        self.assertEqual(result["label"], "ambiguous_reference_match")
        self.assertGreater(result["calibrated_reference_margin_threshold"], 0.05)
        self.assertLess(
            result["reference_margin_vs_best_alternative"],
            result["calibrated_reference_margin_threshold"],
        )

    def test_excludes_invalid_anchor_from_ranking(self) -> None:
        samples = [
            build_sample("official", "exact_alpha", "alpha-17"),
            build_sample("official", "reasoning_note", "reference baseline note"),
            build_sample("official_gpt52", "exact_alpha", "beta-22"),
            build_sample("official_gpt52", "reasoning_note", "lower tier wording"),
            build_sample("official_gpt54_compact", "exact_alpha", "", success=False),
            build_sample("official_gpt54_compact", "reasoning_note", "", success=False),
            build_sample("proxy", "exact_alpha", "alpha-17"),
            build_sample("proxy", "reasoning_note", "reference baseline note"),
        ]
        result = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52", "official_gpt54_compact"],
            category_weights=self.weights,
            fingerprinting=self.fingerprinting,
            max_anchor_failure_rate=0.3,
        )
        self.assertEqual(result["label"], "reference_nearest_neighbor")
        self.assertEqual(result["best_alternative_provider"], "official_gpt52")
        self.assertEqual(result["eligible_anchor_count"], 2)
        self.assertEqual(result["excluded_anchors"][0]["provider"], "official_gpt54_compact")
        self.assertEqual(result["excluded_anchors"][0]["reason"], "no_successful_samples")

    def test_subject_without_successful_samples_returns_insufficient_evidence(self) -> None:
        samples = [
            build_sample("official", "exact_alpha", "alpha-17"),
            build_sample("official", "reasoning_note", "reference baseline note"),
            build_sample("official_gpt52", "exact_alpha", "beta-22"),
            build_sample("official_gpt52", "reasoning_note", "lower tier wording"),
            build_sample("proxy", "exact_alpha", "", success=False),
            build_sample("proxy", "reasoning_note", "", success=False),
        ]
        result = compare_provider_to_anchors(
            self.suite,
            samples,
            subject_provider="proxy",
            reference_provider="official",
            anchor_providers=["official", "official_gpt52"],
            category_weights=self.weights,
            fingerprinting=self.fingerprinting,
            max_anchor_failure_rate=0.3,
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["label"], "insufficient_evidence")
        self.assertIn("subject provider has no successful samples", result["reasons"])

    def test_render_markdown_includes_fingerprint_summary(self) -> None:
        report = render_markdown_report(
            AuditRun(
                run_id="run-1",
                created_at="2026-04-19T18:00:00+0800",
                config_name="demo",
                claimed_model="gpt-5.4",
                reference_provider="official",
                target_providers=["proxy"],
                prompt_suite_name="fingerprint-test",
                reference_calibration={"calibrated_case_count": 1, "uncalibrated_case_count": 0, "category_baselines": {}},
                provider_snapshots={
                    "proxy": ProviderSnapshot(
                        provider="proxy",
                        kind="openai_compatible",
                        requested_model="gpt-5.4",
                        base_url="https://example.test",
                        health={"ok": True},
                        models={"data": [{"id": "gpt-5.4"}]},
                    )
                },
                samples=[build_sample("proxy", "exact_alpha", "alpha-17")],
                analyses=[
                    TargetAnalysis(
                        provider="proxy",
                        role="target",
                        metadata={},
                        aggregate={
                            "weighted_relative_similarity": 1.0,
                            "cross_similarity_ratio": 1.0,
                            "weighted_tail_probability": 1.0,
                            "outlier_case_count": 0,
                            "calibrated_case_count": 1,
                            "mean_failure_rate": 0.0,
                            "mean_json_pass_delta": 0.0,
                            "mean_expectation_pass_delta": 0.0,
                        },
                        verdict={"label": "likely_match", "reasons": ["ok"]},
                        negative_control_comparison={},
                        cases=[
                            CaseAnalysis(
                                case_id="audit_brief_bullets",
                                category="structure",
                                reference_outputs=["- baseline check\n- drift check\n- compare outputs"],
                                target_outputs=["- baseline check\n- drift check\n- compare outputs"],
                                reference_sample_count=1,
                                target_sample_count=1,
                                reference_self_similarity=1.0,
                                reference_baseline_similarity=1.0,
                                cross_similarity=1.0,
                                relative_similarity=1.0,
                                empirical_tail_probability=1.0,
                                exact_match_rate=1.0,
                                reference_json_pass_rate=None,
                                target_json_pass_rate=None,
                                failure_rate=0.0,
                                calibrated=True,
                                reference_expectation_pass_rate=1.0,
                                target_expectation_pass_rate=1.0,
                                discriminator_type="compressed-structure",
                                tags=["audit", "structure"],
                                notes=None,
                            )
                        ],
                        fingerprint={
                            "reasons": ["reference provider remains the nearest known anchor"],
                            "available": True,
                            "label": "reference_nearest_neighbor",
                            "nearest_anchor_provider": "official",
                            "nearest_anchor_similarity": 0.91,
                            "open_set_suspicious": False,
                            "open_set_similarity_threshold_used": 0.33,
                            "open_set_threshold_source": "reference_anchor_calibration",
                            "reference_similarity": 0.91,
                            "best_reference_negative_similarity": 0.72,
                            "calibrated_reference_margin_threshold": 0.06,
                            "best_alternative_provider": "official_gpt52",
                            "best_alternative_similarity": 0.72,
                            "reference_margin_vs_best_alternative": 0.19,
                            "excluded_anchors": [{"provider": "official_gpt54_compact", "reason": "no_successful_samples"}],
                        },
                    )
                ],
            )
        )
        self.assertIn("Fingerprint label", report)
        self.assertIn("Fingerprint nearest anchor", report)
        self.assertIn("Fingerprint excluded anchors", report)
        self.assertIn("Fingerprint calibrated margin threshold", report)
        self.assertIn("Fingerprint open-set threshold used", report)
        self.assertIn("reference_anchor_calibration", report)
        self.assertIn("compressed-structure", report)
        self.assertIn("audit, structure", report)
        self.assertIn("target expectation pass", report)


if __name__ == "__main__":
    unittest.main()
