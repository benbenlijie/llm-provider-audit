from __future__ import annotations

from ..domain import CaseAnalysis


def aggregate_case_metrics(
    cases: list[CaseAnalysis],
    category_weights: dict[str, float],
    outlier_case_pvalue_threshold: float,
) -> dict[str, float]:
    def weight_for(category: str) -> float:
        return float(category_weights.get(category, 1.0))

    def weighted_mean(values: list[tuple[float, float]]) -> float:
        total_weight = sum(weight for _, weight in values)
        if total_weight <= 0:
            return 0.0
        return sum(value * weight for value, weight in values) / total_weight

    if not cases:
        return {
            "mean_reference_self_similarity": 0.0,
            "mean_reference_baseline_similarity": 0.0,
            "mean_cross_similarity": 0.0,
            "cross_similarity_ratio": 0.0,
            "mean_exact_match_rate": 0.0,
            "mean_failure_rate": 1.0,
            "mean_json_pass_delta": 0.0,
            "mean_expectation_pass_delta": 0.0,
            "calibrated_case_count": 0,
            "weighted_relative_similarity": 0.0,
            "weighted_tail_probability": 0.0,
            "outlier_case_count": 0,
        }

    reference_self = weighted_mean([(case.reference_self_similarity, weight_for(case.category)) for case in cases])
    reference_baseline = weighted_mean(
        [
            ((case.reference_baseline_similarity if case.reference_baseline_similarity is not None else case.reference_self_similarity), weight_for(case.category))
            for case in cases
        ]
    )
    cross = weighted_mean([(case.cross_similarity, weight_for(case.category)) for case in cases])
    json_deltas: list[tuple[float, float]] = []
    expectation_deltas: list[tuple[float, float]] = []
    relative_scores: list[tuple[float, float]] = []
    tail_probabilities: list[tuple[float, float]] = []
    calibrated_case_count = 0
    outlier_case_count = 0
    for case in cases:
        if case.reference_json_pass_rate is None or case.target_json_pass_rate is None:
            pass
        else:
            json_deltas.append((abs(case.reference_json_pass_rate - case.target_json_pass_rate), weight_for(case.category)))
        if case.reference_expectation_pass_rate is None or case.target_expectation_pass_rate is None:
            pass
        else:
            expectation_deltas.append(
                (abs(case.reference_expectation_pass_rate - case.target_expectation_pass_rate), weight_for(case.category))
            )
        if case.calibrated and case.relative_similarity is not None:
            calibrated_case_count += 1
            relative_scores.append((case.relative_similarity, weight_for(case.category)))
        if case.empirical_tail_probability is not None:
            tail_probabilities.append((case.empirical_tail_probability, weight_for(case.category)))
            if case.empirical_tail_probability < outlier_case_pvalue_threshold:
                outlier_case_count += 1

    return {
        "mean_reference_self_similarity": reference_self,
        "mean_reference_baseline_similarity": reference_baseline,
        "mean_cross_similarity": cross,
        "cross_similarity_ratio": cross / reference_baseline if reference_baseline > 0 else 0.0,
        "mean_exact_match_rate": weighted_mean([(case.exact_match_rate, weight_for(case.category)) for case in cases]),
        "mean_failure_rate": weighted_mean([(case.failure_rate, weight_for(case.category)) for case in cases]),
        "mean_json_pass_delta": weighted_mean(json_deltas) if json_deltas else 0.0,
        "mean_expectation_pass_delta": weighted_mean(expectation_deltas) if expectation_deltas else 0.0,
        "calibrated_case_count": calibrated_case_count,
        "weighted_relative_similarity": weighted_mean(relative_scores) if relative_scores else 0.0,
        "weighted_tail_probability": weighted_mean(tail_probabilities) if tail_probabilities else 0.0,
        "outlier_case_count": outlier_case_count,
    }
