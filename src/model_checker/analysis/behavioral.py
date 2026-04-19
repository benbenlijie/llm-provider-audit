from __future__ import annotations

from collections import defaultdict
from statistics import mean

from ..domain import CaseAnalysis, PromptSuite, SampleResult
from ..providers.openai_compatible import similarity_ratio
from ..sampling.normalizer import json_passes_expectations, text_passes_expectations


def _group_by_case(samples: list[SampleResult]) -> dict[str, list[SampleResult]]:
    grouped: dict[str, list[SampleResult]] = defaultdict(list)
    for sample in samples:
        grouped[sample.case_id].append(sample)
    return grouped


def _mean_pairwise_similarity(outputs: list[str]) -> float:
    if len(outputs) <= 1:
        return 1.0 if outputs else 0.0
    ratios = []
    for index, left in enumerate(outputs):
        for right in outputs[index + 1 :]:
            ratios.append(similarity_ratio(left, right))
    return mean(ratios) if ratios else 0.0


def _leave_one_out_baseline_scores(outputs: list[str]) -> list[float]:
    if len(outputs) <= 1:
        return []
    scores: list[float] = []
    for index, left in enumerate(outputs):
        others = outputs[:index] + outputs[index + 1 :]
        scores.append(max(similarity_ratio(left, other) for other in others))
    return scores


def analyze_behavior(
    prompt_suite: PromptSuite,
    reference_samples: list[SampleResult],
    target_samples: list[SampleResult],
    *,
    min_reference_samples: int,
) -> list[CaseAnalysis]:
    reference_by_case = _group_by_case(reference_samples)
    target_by_case = _group_by_case(target_samples)
    analyses: list[CaseAnalysis] = []

    for case in prompt_suite.cases:
        ref_items = reference_by_case.get(case.case_id, [])
        target_items = target_by_case.get(case.case_id, [])
        ref_outputs = [item.normalized_text for item in ref_items if item.success]
        target_outputs = [item.normalized_text for item in target_items if item.success]

        ref_self = _mean_pairwise_similarity(ref_outputs)
        baseline_scores = _leave_one_out_baseline_scores(ref_outputs)
        baseline_mean = mean(baseline_scores) if baseline_scores else None
        cross_ratios = []
        for target_output in target_outputs:
            if not ref_outputs:
                cross_ratios.append(0.0)
                continue
            cross_ratios.append(max(similarity_ratio(target_output, ref_output) for ref_output in ref_outputs))
        target_mean = mean(cross_ratios) if cross_ratios else 0.0
        tail_probability = None
        if baseline_scores and cross_ratios:
            tail_probability = (1 + sum(1 for score in baseline_scores if score <= target_mean)) / (len(baseline_scores) + 1)

        exact_match_rate = 0.0
        if target_outputs:
            exact_match_rate = sum(1 for item in target_outputs if item in set(ref_outputs)) / len(target_outputs)

        ref_json = [json_passes_expectations(item.text, case.expectations) for item in ref_items if item.success]
        target_json = [json_passes_expectations(item.text, case.expectations) for item in target_items if item.success]
        ref_expectations = [text_passes_expectations(item.text, case.expectations) for item in ref_items if item.success]
        target_expectations = [text_passes_expectations(item.text, case.expectations) for item in target_items if item.success]

        def _rate(values: list[bool | None]) -> float | None:
            filtered = [item for item in values if item is not None]
            if not filtered:
                return None
            return sum(1 for item in filtered if item) / len(filtered)

        failure_rate = 0.0
        if target_items:
            failure_rate = sum(1 for item in target_items if not item.success) / len(target_items)

        analyses.append(
            CaseAnalysis(
                case_id=case.case_id,
                category=case.category,
                reference_outputs=ref_outputs,
                target_outputs=target_outputs,
                reference_sample_count=len(ref_outputs),
                target_sample_count=len(target_outputs),
                reference_self_similarity=ref_self,
                reference_baseline_similarity=baseline_mean,
                cross_similarity=target_mean,
                relative_similarity=(
                    (target_mean / baseline_mean)
                    if cross_ratios and baseline_mean and baseline_mean > 0 and len(ref_outputs) >= min_reference_samples
                    else None
                ),
                empirical_tail_probability=tail_probability,
                exact_match_rate=exact_match_rate,
                reference_json_pass_rate=_rate(ref_json),
                target_json_pass_rate=_rate(target_json),
                failure_rate=failure_rate,
                calibrated=len(ref_outputs) >= min_reference_samples,
                reference_expectation_pass_rate=_rate(ref_expectations),
                target_expectation_pass_rate=_rate(target_expectations),
                discriminator_type=case.discriminator_type,
                tags=list(case.tags),
                notes=case.notes,
            )
        )

    return analyses
