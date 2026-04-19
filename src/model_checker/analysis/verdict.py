from __future__ import annotations

from ..domain import CalibrationConfig, ScoringConfig


def determine_verdict(
    aggregate: dict[str, float],
    scoring: ScoringConfig,
    calibration: CalibrationConfig,
    negative_control_comparison: dict[str, object] | None = None,
) -> dict[str, object]:
    reasons: list[str] = []
    ratio = float(aggregate.get("weighted_relative_similarity", aggregate.get("cross_similarity_ratio", 0.0)))
    failure_rate = float(aggregate.get("mean_failure_rate", 1.0))
    json_delta = float(aggregate.get("mean_json_pass_delta", 0.0))
    calibrated_case_count = int(aggregate.get("calibrated_case_count", 0))
    weighted_tail_probability = float(aggregate.get("weighted_tail_probability", 0.0))
    outlier_case_count = int(aggregate.get("outlier_case_count", 0))

    if calibrated_case_count < calibration.min_calibrated_cases:
        reasons.append("reference calibration evidence is insufficient")
        if failure_rate > scoring.max_failure_rate:
            reasons.append("target provider failure rate is too high")
        return {
            "label": "insufficient_evidence",
            "reasons": reasons,
        }

    if failure_rate > scoring.max_failure_rate:
        reasons.append("target provider failure rate is too high")
        return {
            "label": "insufficient_evidence",
            "reasons": reasons,
        }

    if weighted_tail_probability <= scoring.severe_weighted_tail_probability:
        reasons.append("target similarity falls below calibrated reference distribution")
        return {
            "label": "strong_mismatch",
            "reasons": reasons,
        }

    if outlier_case_count >= scoring.max_outlier_case_count:
        reasons.append("too many calibrated cases look like outliers against the reference distribution")
        return {
            "label": "strong_mismatch",
            "reasons": reasons,
        }

    if ratio >= scoring.likely_match_similarity_ratio and json_delta <= scoring.max_json_pass_delta:
        margin = None
        if negative_control_comparison:
            margin = negative_control_comparison.get("relative_margin_vs_best_negative")
        if isinstance(margin, (float, int)) and margin < scoring.min_negative_control_margin:
            reasons.append("target is not clearly more reference-like than the best negative control")
            return {
                "label": "suspicious_mismatch",
                "reasons": reasons,
            }
        reasons.append("target behavior stays within calibrated reference drift")
        return {
            "label": "likely_match",
            "reasons": reasons,
        }

    if (
        ratio < scoring.suspicious_similarity_ratio
        or json_delta > scoring.max_json_pass_delta * 1.5
        or weighted_tail_probability < scoring.min_weighted_tail_probability
    ):
        reasons.append("behavioral drift is significantly larger than configured threshold")
        if json_delta > scoring.max_json_pass_delta * 1.5:
            reasons.append("JSON conformance drift is severe")
        if weighted_tail_probability < scoring.min_weighted_tail_probability:
            reasons.append("target sits too low in the calibrated reference similarity distribution")
        return {
            "label": "strong_mismatch",
            "reasons": reasons,
        }

    reasons.append("provider differs from reference but evidence is not decisive")
    return {
        "label": "suspicious_mismatch",
        "reasons": reasons,
    }
