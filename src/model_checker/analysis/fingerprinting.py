from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ..domain import FingerprintConfig, PromptSuite, SampleResult
from ..providers.openai_compatible import similarity_ratio


def group_samples_by_provider_case(samples: list[SampleResult]) -> dict[str, dict[str, list[SampleResult]]]:
    grouped: dict[str, dict[str, list[SampleResult]]] = defaultdict(lambda: defaultdict(list))
    for sample in samples:
        grouped[sample.provider][sample.case_id].append(sample)
    return grouped


def _case_similarity(left_samples: list[SampleResult], right_samples: list[SampleResult]) -> float:
    left_outputs = [sample.normalized_text for sample in left_samples if sample.success and sample.normalized_text]
    right_outputs = [sample.normalized_text for sample in right_samples if sample.success and sample.normalized_text]
    if not left_outputs or not right_outputs:
        return 0.0

    def directed_similarity(source: list[str], target: list[str]) -> float:
        return mean(max(similarity_ratio(left, right) for right in target) for left in source)

    return mean(
        [
            directed_similarity(left_outputs, right_outputs),
            directed_similarity(right_outputs, left_outputs),
        ]
    )


def provider_sample_stats(provider_cases: dict[str, list[SampleResult]]) -> dict[str, float | int]:
    all_samples = [sample for samples in provider_cases.values() for sample in samples]
    total_samples = len(all_samples)
    successful_samples = [sample for sample in all_samples if sample.success and sample.normalized_text]
    successful_case_count = sum(
        1
        for samples in provider_cases.values()
        if any(sample.success and sample.normalized_text for sample in samples)
    )
    failure_count = sum(1 for sample in all_samples if not sample.success)
    failure_rate = (failure_count / total_samples) if total_samples else 1.0
    return {
        "total_samples": total_samples,
        "successful_sample_count": len(successful_samples),
        "successful_case_count": successful_case_count,
        "failure_rate": failure_rate,
    }


def weighted_provider_similarity(
    prompt_suite: PromptSuite,
    samples_by_provider_case: dict[str, dict[str, list[SampleResult]]],
    *,
    left_provider: str,
    right_provider: str,
    category_weights: dict[str, float],
) -> float:
    left_cases = samples_by_provider_case.get(left_provider, {})
    right_cases = samples_by_provider_case.get(right_provider, {})
    case_scores: list[tuple[float, float]] = []
    for case in prompt_suite.cases:
        weight = float(category_weights.get(case.category, 1.0))
        score = _case_similarity(left_cases.get(case.case_id, []), right_cases.get(case.case_id, []))
        case_scores.append((score, weight))
    total_weight = sum(weight for _, weight in case_scores)
    if total_weight <= 0:
        return 0.0
    return sum(score * weight for score, weight in case_scores) / total_weight


def compare_provider_to_anchors(
    prompt_suite: PromptSuite,
    samples: list[SampleResult],
    *,
    subject_provider: str,
    reference_provider: str,
    anchor_providers: list[str],
    category_weights: dict[str, float],
    fingerprinting: FingerprintConfig,
    max_anchor_failure_rate: float,
    reference_anchor_calibration: dict[str, object] | None = None,
) -> dict[str, object]:
    if not fingerprinting.enabled:
        return {"available": False, "label": "disabled", "reasons": ["fingerprinting is disabled"]}

    samples_by_provider_case = group_samples_by_provider_case(samples)
    subject_cases = samples_by_provider_case.get(subject_provider)
    if not subject_cases:
        return {"available": False, "label": "insufficient_evidence", "reasons": ["subject provider has no samples"]}
    subject_stats = provider_sample_stats(subject_cases)
    if int(subject_stats["successful_sample_count"]) == 0:
        return {
            "available": False,
            "label": "insufficient_evidence",
            "reasons": ["subject provider has no successful samples"],
            "subject_stats": subject_stats,
        }

    ranked_anchors: list[dict[str, object]] = []
    excluded_anchors: list[dict[str, object]] = []
    for anchor_provider in anchor_providers:
        if anchor_provider == subject_provider:
            continue
        anchor_cases = samples_by_provider_case.get(anchor_provider)
        if not anchor_cases:
            excluded_anchors.append(
                {
                    "provider": anchor_provider,
                    "reason": "no_samples",
                }
            )
            continue
        anchor_stats = provider_sample_stats(anchor_cases)
        if int(anchor_stats["successful_sample_count"]) == 0:
            excluded_anchors.append(
                {
                    "provider": anchor_provider,
                    "reason": "no_successful_samples",
                    "failure_rate": anchor_stats["failure_rate"],
                }
            )
            continue
        if float(anchor_stats["failure_rate"]) > max_anchor_failure_rate:
            excluded_anchors.append(
                {
                    "provider": anchor_provider,
                    "reason": "failure_rate_above_threshold",
                    "failure_rate": anchor_stats["failure_rate"],
                }
            )
            continue
        weighted_similarity = weighted_provider_similarity(
            prompt_suite,
            samples_by_provider_case,
            left_provider=subject_provider,
            right_provider=anchor_provider,
            category_weights=category_weights,
        )
        ranked_anchors.append(
            {
                "provider": anchor_provider,
                "weighted_similarity": weighted_similarity,
            }
        )

    if not ranked_anchors:
        return {
            "available": False,
            "label": "insufficient_evidence",
            "reasons": ["no eligible anchor providers remain after filtering"],
            "excluded_anchors": excluded_anchors,
            "subject_stats": subject_stats,
        }

    ranked_anchors.sort(key=lambda item: float(item["weighted_similarity"]), reverse=True)
    nearest_anchor = ranked_anchors[0]
    reference_entry = next(
        (item for item in ranked_anchors if item["provider"] == reference_provider),
        None,
    )
    if reference_entry is None:
        return {
            "available": False,
            "label": "insufficient_evidence",
            "reasons": ["reference anchor is not eligible for fingerprint comparison"],
            "nearest_anchor_provider": nearest_anchor["provider"],
            "nearest_anchor_similarity": float(nearest_anchor["weighted_similarity"]),
            "excluded_anchors": excluded_anchors,
            "subject_stats": subject_stats,
            "ranked_anchors": ranked_anchors,
        }
    alternatives = [item for item in ranked_anchors if item["provider"] != reference_provider]
    best_alternative = alternatives[0] if alternatives else None
    reference_similarity = float(reference_entry["weighted_similarity"]) if reference_entry is not None else None
    best_alternative_similarity = (
        float(best_alternative["weighted_similarity"]) if best_alternative is not None else None
    )
    reference_margin = (
        reference_similarity - best_alternative_similarity
        if reference_similarity is not None and best_alternative_similarity is not None
        else None
    )
    nearest_similarity = float(nearest_anchor["weighted_similarity"])
    open_set_threshold_used = fingerprinting.open_set_min_anchor_similarity
    open_set_threshold_source = "config"
    if reference_anchor_calibration and bool(reference_anchor_calibration.get("available")):
        calibrated_open_set_threshold = reference_anchor_calibration.get("open_set_threshold_to_apply")
        if isinstance(calibrated_open_set_threshold, (float, int)):
            open_set_threshold_used = min(open_set_threshold_used, float(calibrated_open_set_threshold))
            open_set_threshold_source = "reference_anchor_calibration"
    open_set_suspicious = nearest_similarity < open_set_threshold_used
    calibration_anchors = [item for item in ranked_anchors if item["provider"] != reference_provider]
    best_reference_negative_similarity = None
    calibrated_reference_margin_threshold = fingerprinting.min_reference_margin
    if calibration_anchors:
        best_reference_negative_similarity = max(
            weighted_provider_similarity(
                prompt_suite,
                samples_by_provider_case,
                left_provider=reference_provider,
                right_provider=item["provider"],
                category_weights=category_weights,
            )
            for item in calibration_anchors
        )
        separation = max(0.0, 1.0 - best_reference_negative_similarity)
        calibrated_reference_margin_threshold = max(
            fingerprinting.min_reference_margin,
            fingerprinting.reference_margin_scale * separation,
        )

    reasons: list[str] = []
    label = "reference_nearest_neighbor"
    if open_set_suspicious:
        label = "open_set_suspicious"
        reasons.append("nearest anchor similarity is below the active open-set threshold")
    elif nearest_anchor["provider"] != reference_provider:
        label = "closest_non_reference_anchor"
        reasons.append("nearest anchor is not the configured reference provider")
    elif reference_margin is not None and reference_margin < calibrated_reference_margin_threshold:
        label = "ambiguous_reference_match"
        reasons.append("reference margin over the best alternative anchor is below the calibrated threshold")
    else:
        reasons.append("reference provider remains the nearest known anchor")

    return {
        "available": True,
        "label": label,
        "reasons": reasons,
        "eligible_anchor_count": len(ranked_anchors),
        "excluded_anchors": excluded_anchors,
        "subject_stats": subject_stats,
        "nearest_anchor_provider": nearest_anchor["provider"],
        "nearest_anchor_similarity": nearest_similarity,
        "reference_provider": reference_provider,
        "reference_similarity": reference_similarity,
        "best_reference_negative_similarity": best_reference_negative_similarity,
        "calibrated_reference_margin_threshold": calibrated_reference_margin_threshold,
        "best_alternative_provider": best_alternative["provider"] if best_alternative is not None else None,
        "best_alternative_similarity": best_alternative_similarity,
        "reference_margin_vs_best_alternative": reference_margin,
        "open_set_suspicious": open_set_suspicious,
        "open_set_similarity_threshold_used": open_set_threshold_used,
        "open_set_threshold_source": open_set_threshold_source,
        "ranked_anchors": ranked_anchors,
    }
