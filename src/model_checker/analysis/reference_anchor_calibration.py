from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from statistics import mean

from ..domain import AnchorCalibrationConfig, FingerprintConfig, PromptSuite, SampleResult
from .fingerprinting import (
    group_samples_by_provider_case,
    provider_sample_stats,
    weighted_provider_similarity,
)


def _quantile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("quantile requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    clamped = min(max(quantile, 0.0), 1.0)
    position = clamped * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize_reference_anchor_calibration(
    prompt_suite: PromptSuite,
    reference_provider: str,
    batch_samples: list[list[SampleResult]],
    *,
    category_weights: dict[str, float],
    fingerprinting: FingerprintConfig,
    anchor_calibration: AnchorCalibrationConfig,
) -> dict[str, object]:
    relabeled_samples: list[SampleResult] = []
    batch_labels: list[str] = []
    for index, samples in enumerate(batch_samples, start=1):
        batch_label = f"{reference_provider}__anchor_batch_{index}"
        batch_labels.append(batch_label)
        relabeled_samples.extend(replace(sample, provider=batch_label) for sample in samples)

    samples_by_provider_case = group_samples_by_provider_case(relabeled_samples)
    batches = []
    for batch_label in batch_labels:
        stats = provider_sample_stats(samples_by_provider_case.get(batch_label, {}))
        batches.append(
            {
                "batch_id": batch_label,
                "total_samples": int(stats["total_samples"]),
                "successful_sample_count": int(stats["successful_sample_count"]),
                "successful_case_count": int(stats["successful_case_count"]),
                "failure_rate": float(stats["failure_rate"]),
            }
        )

    pairwise_similarities: list[dict[str, object]] = []
    pairwise_values: list[float] = []
    for left_batch, right_batch in combinations(batch_labels, 2):
        similarity = weighted_provider_similarity(
            prompt_suite,
            samples_by_provider_case,
            left_provider=left_batch,
            right_provider=right_batch,
            category_weights=category_weights,
        )
        pairwise_values.append(similarity)
        pairwise_similarities.append(
            {
                "left_batch": left_batch,
                "right_batch": right_batch,
                "weighted_similarity": similarity,
            }
        )

    if not pairwise_values:
        return {
            "available": False,
            "reasons": ["anchor calibration requires at least two reference batches"],
            "configured_open_set_threshold": fingerprinting.open_set_min_anchor_similarity,
            "batch_count": len(batch_labels),
            "batches": batches,
            "pairwise_batch_similarities": pairwise_similarities,
        }

    quantile_similarity = _quantile(pairwise_values, anchor_calibration.similarity_quantile)
    suggested_threshold = max(0.0, quantile_similarity - anchor_calibration.threshold_margin)
    threshold_to_apply = min(fingerprinting.open_set_min_anchor_similarity, suggested_threshold)
    return {
        "available": True,
        "batch_count": len(batch_labels),
        "batch_repetitions": anchor_calibration.batch_repetitions,
        "inter_batch_cooldown_ms": anchor_calibration.inter_batch_cooldown_ms,
        "similarity_quantile": anchor_calibration.similarity_quantile,
        "threshold_margin": anchor_calibration.threshold_margin,
        "configured_open_set_threshold": fingerprinting.open_set_min_anchor_similarity,
        "pairwise_similarity_mean": mean(pairwise_values),
        "pairwise_similarity_min": min(pairwise_values),
        "pairwise_similarity_max": max(pairwise_values),
        "pairwise_similarity_quantile": quantile_similarity,
        "suggested_open_set_similarity_threshold": suggested_threshold,
        "open_set_threshold_to_apply": threshold_to_apply,
        "batches": batches,
        "pairwise_batch_similarities": pairwise_similarities,
    }
