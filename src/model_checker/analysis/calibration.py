from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ..domain import CalibrationConfig, PromptSuite, SampleResult
from ..providers.openai_compatible import similarity_ratio


def summarize_reference_calibration(
    prompt_suite: PromptSuite,
    reference_samples: list[SampleResult],
    calibration: CalibrationConfig,
) -> dict[str, object]:
    by_case: dict[str, list[SampleResult]] = defaultdict(list)
    for sample in reference_samples:
        by_case[sample.case_id].append(sample)

    cases: list[dict[str, object]] = []
    category_buckets: dict[str, list[float]] = defaultdict(list)

    for case in prompt_suite.cases:
        items = by_case.get(case.case_id, [])
        outputs = [item.normalized_text for item in items if item.success]
        sample_count = len(outputs)
        self_similarity: float | None = None

        if sample_count >= 2:
            scores: list[float] = []
            for index, left in enumerate(outputs):
                for right in outputs[index + 1 :]:
                    scores.append(similarity_ratio(left, right))
            self_similarity = mean(scores) if scores else 1.0

        calibrated = sample_count >= calibration.min_reference_samples and self_similarity is not None
        if calibrated and self_similarity is not None:
            category_buckets[case.category].append(self_similarity)

        cases.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "reference_sample_count": sample_count,
                "calibrated": calibrated,
                "reference_self_similarity": self_similarity,
            }
        )

    category_baselines = {
        category: mean(values)
        for category, values in category_buckets.items()
        if values
    }
    calibrated_case_count = sum(1 for item in cases if item["calibrated"])
    return {
        "min_reference_samples": calibration.min_reference_samples,
        "min_calibrated_cases": calibration.min_calibrated_cases,
        "category_weights": calibration.category_weights,
        "calibrated_case_count": calibrated_case_count,
        "uncalibrated_case_count": len(cases) - calibrated_case_count,
        "category_baselines": category_baselines,
        "cases": cases,
    }
