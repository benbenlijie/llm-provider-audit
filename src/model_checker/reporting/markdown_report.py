from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..domain import AuditRun, SampleResult, TargetAnalysis


def _shorten(text: str, limit: int = 220) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3]}..."


def _dominant_failure(samples: list[SampleResult], provider: str) -> tuple[str, int, int] | None:
    failed_samples = [sample for sample in samples if sample.provider == provider and not sample.success and sample.error]
    if not failed_samples:
        return None
    counts = Counter(sample.error for sample in failed_samples if sample.error)
    if not counts:
        return None
    error, count = counts.most_common(1)[0]
    return error, count, len(failed_samples)


def _render_analysis(lines: list[str], run: AuditRun, analysis: TargetAnalysis, *, heading_prefix: str) -> None:
    dominant_failure = _dominant_failure(run.samples, analysis.provider)
    snapshot = run.provider_snapshots.get(analysis.provider)
    requested_model = analysis.metadata.get("target_requested_model", run.claimed_model)
    requested_model_listed = bool(analysis.metadata.get("target_requested_model_listed", False))
    provider_health_ok = bool(analysis.metadata.get("target_health_ok", False))
    if snapshot is not None:
        requested_model = snapshot.requested_model
        provider_health_ok = bool(snapshot.health.get("ok", True)) if isinstance(snapshot.health, dict) else False
        target_models = snapshot.models.get("data", []) if isinstance(snapshot.models, dict) else []
        target_model_ids = {item.get("id") for item in target_models if isinstance(item, dict)}
        requested_model_listed = requested_model in target_model_ids
    lines.extend(
        [
            f"## {heading_prefix}: `{analysis.provider}`",
            "",
            f"- Verdict: `{analysis.verdict['label']}`",
            f"- Requested model: `{requested_model}`",
            f"- Requested model listed in `/v1/models`: `{requested_model_listed}`",
            f"- Provider health OK: `{provider_health_ok}`",
            f"- Weighted relative similarity: `{analysis.aggregate['weighted_relative_similarity']:.3f}`",
            f"- Weighted cross similarity ratio: `{analysis.aggregate['cross_similarity_ratio']:.3f}`",
            f"- Weighted tail probability: `{analysis.aggregate.get('weighted_tail_probability', 0.0):.3f}`",
            f"- Outlier case count: `{analysis.aggregate.get('outlier_case_count', 0)}`",
            f"- Calibrated cases used: `{analysis.aggregate['calibrated_case_count']}`",
            f"- Mean failure rate: `{analysis.aggregate['mean_failure_rate']:.3f}`",
            f"- Mean JSON pass delta: `{analysis.aggregate['mean_json_pass_delta']:.3f}`",
            f"- Mean expectation pass delta: `{analysis.aggregate.get('mean_expectation_pass_delta', 0.0):.3f}`",
            f"- Reasons: {', '.join(analysis.verdict['reasons'])}",
        ]
    )
    if dominant_failure is not None:
        error, count, total = dominant_failure
        lines.append(f"- Dominant error: `{_shorten(error, limit=180)}` (`{count}/{total}` failed samples)")
    if analysis.role == "target" and analysis.negative_control_comparison.get("available"):
        lines.extend(
            [
                f"- Best negative control: `{analysis.negative_control_comparison['best_negative_provider']}`",
                f"- Relative margin vs best negative: `{analysis.negative_control_comparison['relative_margin_vs_best_negative']:.3f}`",
            ]
        )
    fingerprint = analysis.fingerprint or {}
    if fingerprint:
        lines.append(f"- Fingerprint available: `{fingerprint.get('available', False)}`")
        if fingerprint.get("label") is not None:
            lines.append(f"- Fingerprint label: `{fingerprint['label']}`")
        if fingerprint.get("reasons"):
            lines.append(f"- Fingerprint reasons: {', '.join(str(item) for item in fingerprint['reasons'])}")
    if fingerprint.get("available"):
        lines.extend(
            [
                f"- Fingerprint nearest anchor: `{fingerprint['nearest_anchor_provider']}`",
                f"- Fingerprint nearest anchor similarity: `{fingerprint['nearest_anchor_similarity']:.3f}`",
                f"- Fingerprint open-set suspicious: `{fingerprint['open_set_suspicious']}`",
            ]
        )
        open_set_threshold_used = fingerprint.get("open_set_similarity_threshold_used")
        if isinstance(open_set_threshold_used, (float, int)):
            lines.append(f"- Fingerprint open-set threshold used: `{open_set_threshold_used:.3f}`")
        open_set_threshold_source = fingerprint.get("open_set_threshold_source")
        if open_set_threshold_source:
            lines.append(f"- Fingerprint open-set threshold source: `{open_set_threshold_source}`")
        reference_similarity = fingerprint.get("reference_similarity")
        if isinstance(reference_similarity, (float, int)):
            lines.append(f"- Fingerprint reference similarity: `{reference_similarity:.3f}`")
        best_reference_negative_similarity = fingerprint.get("best_reference_negative_similarity")
        if isinstance(best_reference_negative_similarity, (float, int)):
            lines.append(
                f"- Fingerprint best reference-negative similarity: `{best_reference_negative_similarity:.3f}`"
            )
        calibrated_reference_margin_threshold = fingerprint.get("calibrated_reference_margin_threshold")
        if isinstance(calibrated_reference_margin_threshold, (float, int)):
            lines.append(
                f"- Fingerprint calibrated margin threshold: `{calibrated_reference_margin_threshold:.3f}`"
            )
        best_alternative_provider = fingerprint.get("best_alternative_provider")
        if best_alternative_provider:
            lines.append(f"- Fingerprint best alternative anchor: `{best_alternative_provider}`")
        best_alternative_similarity = fingerprint.get("best_alternative_similarity")
        if isinstance(best_alternative_similarity, (float, int)):
            lines.append(f"- Fingerprint best alternative similarity: `{best_alternative_similarity:.3f}`")
        reference_margin = fingerprint.get("reference_margin_vs_best_alternative")
        if isinstance(reference_margin, (float, int)):
            lines.append(f"- Fingerprint reference margin: `{reference_margin:.3f}`")
    excluded_anchors = fingerprint.get("excluded_anchors") or []
    if excluded_anchors:
        excluded_summary = ", ".join(
            (
                f"{item['provider']}({item['reason']})"
                if "failure_rate" not in item
                else f"{item['provider']}({item['reason']}:{float(item['failure_rate']):.3f})"
            )
            for item in excluded_anchors
        )
        lines.append(f"- Fingerprint excluded anchors: `{excluded_summary}`")
    lines.extend(
        [
            "",
            "| Case | Category | Type | Tags | Calibrated | Relative Similarity | Tail Prob. | Cross Similarity | Exact Match | Failure Rate |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for case in analysis.cases:
        relative_str = f"{case.relative_similarity:.3f}" if case.relative_similarity is not None else "n/a"
        tail_str = f"{case.empirical_tail_probability:.3f}" if case.empirical_tail_probability is not None else "n/a"
        discriminator = case.discriminator_type or "n/a"
        tags = ", ".join(case.tags) if case.tags else "-"
        lines.append(
            f"| `{case.case_id}` | `{case.category}` | `{discriminator}` | `{tags}` | `{str(case.calibrated).lower()}` | "
            f"`{relative_str}` | `{tail_str}` | `{case.cross_similarity:.3f}` | `{case.exact_match_rate:.3f}` | `{case.failure_rate:.3f}` |"
        )
    lines.extend(["", "### Sample Excerpts", ""])
    ranked_cases = sorted(
        analysis.cases,
        key=lambda item: (
            item.relative_similarity if item.relative_similarity is not None else 999.0,
            item.empirical_tail_probability if item.empirical_tail_probability is not None else 999.0,
            item.cross_similarity,
            item.failure_rate,
        ),
    )
    for case in ranked_cases[:3]:
        reference_excerpt = _shorten(case.reference_outputs[0]) if case.reference_outputs else "<empty>"
        target_excerpt = _shorten(case.target_outputs[0]) if case.target_outputs else "<empty>"
        relative_str = f"{case.relative_similarity:.3f}" if case.relative_similarity is not None else "n/a"
        tail_str = f"{case.empirical_tail_probability:.3f}" if case.empirical_tail_probability is not None else "n/a"
        metadata_bits = []
        if case.discriminator_type:
            metadata_bits.append(f"type `{case.discriminator_type}`")
        if case.tags:
            metadata_bits.append(f"tags `{', '.join(case.tags)}`")
        if case.target_expectation_pass_rate is not None:
            metadata_bits.append(
                f"target expectation pass `{case.target_expectation_pass_rate:.3f}`"
            )
        if case.reference_expectation_pass_rate is not None:
            metadata_bits.append(
                f"reference expectation pass `{case.reference_expectation_pass_rate:.3f}`"
            )
        metadata_suffix = f", {', '.join(metadata_bits)}" if metadata_bits else ""
        lines.extend(
            [
                f"- Case `{case.case_id}` (`{case.category}`), relative similarity `{relative_str}`, tail prob `{tail_str}`{metadata_suffix}",
                f"  Reference: `{reference_excerpt}`",
                f"  Target: `{target_excerpt}`",
            ]
        )
    lines.append("")


def render_markdown_report(run: AuditRun) -> str:
    lines = [
        f"# Audit Report: {run.config_name}",
        "",
        f"- Run ID: `{run.run_id}`",
        f"- Claimed model: `{run.claimed_model}`",
        f"- Reference provider: `{run.reference_provider}`",
        "",
        "## Reference Calibration",
        "",
        f"- Calibrated cases: `{run.reference_calibration.get('calibrated_case_count', 0)}`",
        f"- Uncalibrated cases: `{run.reference_calibration.get('uncalibrated_case_count', 0)}`",
    ]
    for category, baseline in sorted(run.reference_calibration.get("category_baselines", {}).items()):
        lines.append(f"- Baseline `{category}` self similarity: `{baseline:.3f}`")
    lines.append("")

    negative_controls = [analysis for analysis in run.analyses if analysis.role == "negative_control"]
    targets = [analysis for analysis in run.analyses if analysis.role == "target"]

    if negative_controls:
        lines.extend(["## Negative Controls", ""])
        for analysis in negative_controls:
            _render_analysis(lines, run, analysis, heading_prefix="Negative Control")

    if targets:
        lines.extend(["## Targets", ""])
        for analysis in targets:
            _render_analysis(lines, run, analysis, heading_prefix="Target")

    return "\n".join(lines)


def write_markdown_report(run: AuditRun, output_dir: Path) -> Path:
    path = output_dir / "report.md"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(render_markdown_report(run))
    return path
