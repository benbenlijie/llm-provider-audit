from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
from time import sleep

from .analysis.behavioral import analyze_behavior
from .analysis.calibration import summarize_reference_calibration
from .analysis.fingerprinting import compare_provider_to_anchors
from .analysis.metadata import compare_metadata
from .analysis.reference_anchor_calibration import summarize_reference_anchor_calibration
from .analysis.statistics import aggregate_case_metrics
from .analysis.verdict import determine_verdict
from .config import load_audit_config
from .domain import AuditConfig, AuditRun, CaseAnalysis, ProviderSnapshot, SampleResult, TargetAnalysis
from .providers import OpenAICompatibleProvider, RouterInstanceProvider
from .reporting import render_markdown_report, write_json_report, write_markdown_report
from .sampling import collect_provider_samples
from .utils.fs import ensure_dir
from .utils.time import file_timestamp, utc_timestamp


def _load_reference_anchor_calibration(
    path: str | Path | None,
    config: AuditConfig,
) -> dict[str, object] | None:
    if path is None:
        return None
    calibration_path = Path(path).resolve()
    with calibration_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("claimed_model") != config.claimed_model:
        raise ValueError("reference anchor calibration claimed_model does not match current config")
    if payload.get("reference_provider") != config.reference_provider:
        raise ValueError("reference anchor calibration reference_provider does not match current config")
    if payload.get("prompt_suite_name") != config.prompt_suite.name:
        raise ValueError("reference anchor calibration prompt_suite_name does not match current config")
    calibration = payload.get("reference_anchor_calibration")
    if not isinstance(calibration, dict):
        raise ValueError("reference anchor calibration payload is missing reference_anchor_calibration")
    return calibration


def compare_against_negative_controls(
    target_analysis: TargetAnalysis,
    negative_analyses: list[TargetAnalysis],
) -> dict[str, object]:
    if not negative_analyses:
        return {
            "available": False,
            "best_negative_provider": None,
            "best_negative_relative_similarity": None,
            "relative_margin_vs_best_negative": None,
        }

    ranked = sorted(
        negative_analyses,
        key=lambda analysis: analysis.aggregate.get("weighted_relative_similarity", 0.0),
        reverse=True,
    )
    best_negative = ranked[0]
    target_relative = float(target_analysis.aggregate.get("weighted_relative_similarity", 0.0))
    negative_relative = float(best_negative.aggregate.get("weighted_relative_similarity", 0.0))
    return {
        "available": True,
        "best_negative_provider": best_negative.provider,
        "best_negative_relative_similarity": negative_relative,
        "relative_margin_vs_best_negative": target_relative - negative_relative,
        "ranked_negative_controls": [
            {
                "provider": analysis.provider,
                "weighted_relative_similarity": analysis.aggregate.get("weighted_relative_similarity", 0.0),
                "weighted_tail_probability": analysis.aggregate.get("weighted_tail_probability", 0.0),
            }
            for analysis in ranked
        ],
    }


def analyze_provider_against_reference(
    config: AuditConfig,
    provider_name: str,
    provider_snapshots: dict[str, object],
    reference_samples: list[object],
    target_samples: list[object],
    *,
    role: str,
) -> TargetAnalysis:
    target_snapshot = provider_snapshots[provider_name]
    metadata = compare_metadata(
        provider_snapshots[config.reference_provider],
        target_snapshot,
        target_snapshot.requested_model,
    )
    case_results = analyze_behavior(
        config.prompt_suite,
        reference_samples,
        target_samples,
        min_reference_samples=config.calibration.min_reference_samples,
    )
    aggregate = aggregate_case_metrics(
        case_results,
        config.calibration.category_weights,
        config.scoring.outlier_case_pvalue_threshold,
    )
    return TargetAnalysis(
        provider=provider_name,
        role=role,
        metadata=metadata,
        aggregate=aggregate,
        verdict={},
        negative_control_comparison={},
        cases=case_results,
    )


def build_provider(config: AuditConfig, provider_name: str):
    provider_config = config.providers[provider_name]
    requested_model = provider_config.model_override or config.claimed_model
    if provider_config.kind == "router_instance":
        return RouterInstanceProvider(
            provider_config,
            requested_model,
            config.router,
            config.sampling.timeout_sec,
            config.sampling.max_output_tokens,
        )
    if provider_config.kind == "openai_compatible":
        return OpenAICompatibleProvider(
            provider_name,
            requested_model,
            base_url=provider_config.base_url or "",
            timeout_sec=config.sampling.timeout_sec,
            max_output_tokens=config.sampling.max_output_tokens,
            trust_env=provider_config.trust_env,
            api_key_env=provider_config.api_key_env,
            headers=provider_config.headers,
        )
    raise ValueError(f"Unsupported provider kind: {provider_config.kind}")


def run_audit(
    config_path: str | Path,
    *,
    reference_anchor_calibration_path: str | Path | None = None,
) -> tuple[AuditRun, Path]:
    config = load_audit_config(config_path)
    run_id = f"{file_timestamp()}-{config.name}"
    output_dir = ensure_dir(config.report_dir / run_id)
    reference_anchor_calibration = _load_reference_anchor_calibration(reference_anchor_calibration_path, config)

    provider_snapshots = {}
    samples = []
    analyses = []
    samples_by_provider: dict[str, list[SampleResult]] = {}

    with ExitStack() as stack:
        reference_provider = stack.enter_context(build_provider(config, config.reference_provider))
        provider_snapshots[config.reference_provider] = reference_provider.snapshot()
        reference_samples = collect_provider_samples(
            reference_provider,
            config.prompt_suite,
            config.sampling.repetitions,
            config.sampling.cooldown_ms,
        )
        samples.extend(reference_samples)
        samples_by_provider[config.reference_provider] = reference_samples
        reference_calibration = summarize_reference_calibration(
            config.prompt_suite,
            reference_samples,
            config.calibration,
        )

        negative_analyses: list[TargetAnalysis] = []
        for provider_name in config.negative_controls:
            provider = stack.enter_context(build_provider(config, provider_name))
            provider_snapshots[provider_name] = provider.snapshot()
            negative_samples = collect_provider_samples(
                provider,
                config.prompt_suite,
                config.sampling.repetitions,
                config.sampling.cooldown_ms,
            )
            samples.extend(negative_samples)
            samples_by_provider[provider_name] = negative_samples
            negative_analysis = analyze_provider_against_reference(
                config,
                provider_name,
                provider_snapshots,
                reference_samples,
                negative_samples,
                role="negative_control",
            )
            negative_analysis.verdict = determine_verdict(
                negative_analysis.aggregate,
                config.scoring,
                config.calibration,
            )
            negative_analyses.append(negative_analysis)
            analyses.append(negative_analysis)

        for provider_name in config.target_providers:
            provider = stack.enter_context(build_provider(config, provider_name))
            provider_snapshots[provider_name] = provider.snapshot()
            target_samples = collect_provider_samples(
                provider,
                config.prompt_suite,
                config.sampling.repetitions,
                config.sampling.cooldown_ms,
            )
            samples.extend(target_samples)
            samples_by_provider[provider_name] = target_samples
            target_analysis = analyze_provider_against_reference(
                config,
                provider_name,
                provider_snapshots,
                reference_samples,
                target_samples,
                role="target",
            )
            target_analysis.negative_control_comparison = compare_against_negative_controls(target_analysis, negative_analyses)
            target_analysis.verdict = determine_verdict(
                target_analysis.aggregate,
                config.scoring,
                config.calibration,
                negative_control_comparison=target_analysis.negative_control_comparison,
            )
            analyses.append(target_analysis)

        anchor_providers = [config.reference_provider, *config.negative_controls]
        for analysis in analyses:
            provider_samples = samples_by_provider.get(analysis.provider, [])
            if not provider_samples:
                analysis.fingerprint = {
                    "available": False,
                    "label": "insufficient_evidence",
                    "reasons": ["provider has no samples"],
                }
                continue
            analysis.fingerprint = compare_provider_to_anchors(
                config.prompt_suite,
                samples,
                subject_provider=analysis.provider,
                reference_provider=config.reference_provider,
                anchor_providers=anchor_providers,
                category_weights=config.calibration.category_weights,
                fingerprinting=config.fingerprinting,
                max_anchor_failure_rate=config.scoring.max_failure_rate,
                reference_anchor_calibration=reference_anchor_calibration,
            )

    run = AuditRun(
        run_id=run_id,
        created_at=utc_timestamp(),
        config_name=config.name,
        claimed_model=config.claimed_model,
        reference_provider=config.reference_provider,
        target_providers=config.target_providers,
        prompt_suite_name=config.prompt_suite.name,
        reference_calibration=reference_calibration,
        provider_snapshots=provider_snapshots,
        samples=samples,
        analyses=analyses,
    )

    write_json_report(run, output_dir)
    write_markdown_report(run, output_dir)
    return run, output_dir


def run_reference_calibration(config_path: str | Path) -> tuple[dict[str, object], Path]:
    config = load_audit_config(config_path)
    run_id = f"{file_timestamp()}-{config.name}-calibration"
    output_dir = ensure_dir(config.report_dir / run_id)

    with ExitStack() as stack:
        reference_provider = stack.enter_context(build_provider(config, config.reference_provider))
        provider_snapshot = reference_provider.snapshot()
        reference_samples = collect_provider_samples(
            reference_provider,
            config.prompt_suite,
            max(config.sampling.repetitions, config.calibration.min_reference_samples),
            config.sampling.cooldown_ms,
        )

    calibration = summarize_reference_calibration(config.prompt_suite, reference_samples, config.calibration)
    payload = {
        "run_id": run_id,
        "created_at": utc_timestamp(),
        "config_name": config.name,
        "claimed_model": config.claimed_model,
        "reference_provider": config.reference_provider,
        "provider_snapshot": asdict(provider_snapshot),
        "reference_calibration": calibration,
    }
    (output_dir / "calibration.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# Reference Calibration: {config.name}",
        "",
        f"- Run ID: `{run_id}`",
        f"- Claimed model: `{config.claimed_model}`",
        f"- Reference provider: `{config.reference_provider}`",
        f"- Calibrated cases: `{calibration['calibrated_case_count']}`",
        f"- Uncalibrated cases: `{calibration['uncalibrated_case_count']}`",
        "",
        "## Category Baselines",
        "",
    ]
    for category, baseline in sorted(calibration["category_baselines"].items()):
        lines.append(f"- `{category}`: `{baseline:.3f}`")
    lines.extend(["", "## Case Baselines", "", "| Case | Category | Samples | Calibrated | Self Similarity |", "| --- | --- | ---: | ---: | ---: |"])
    for case in calibration["cases"]:
        baseline = case["reference_self_similarity"]
        baseline_str = f"{baseline:.3f}" if isinstance(baseline, (float, int)) else "n/a"
        lines.append(
            f"| `{case['case_id']}` | `{case['category']}` | `{case['reference_sample_count']}` | "
            f"`{str(case['calibrated']).lower()}` | `{baseline_str}` |"
        )
    (output_dir / "calibration.md").write_text("\n".join(lines), encoding="utf-8")
    return payload, output_dir


def run_reference_anchor_calibration(config_path: str | Path) -> tuple[dict[str, object], Path]:
    config = load_audit_config(config_path)
    run_id = f"{file_timestamp()}-{config.name}-reference-anchor-calibration"
    output_dir = ensure_dir(config.report_dir.parent / "anchor-calibrations" / run_id)

    batch_count = max(2, config.anchor_calibration.batch_count)
    batch_repetitions = config.anchor_calibration.batch_repetitions
    if batch_repetitions is None:
        batch_repetitions = max(config.sampling.repetitions, config.calibration.min_reference_samples)

    batch_samples: list[list[SampleResult]] = []
    with ExitStack() as stack:
        reference_provider = stack.enter_context(build_provider(config, config.reference_provider))
        provider_snapshot = reference_provider.snapshot()
        for batch_index in range(batch_count):
            batch_samples.append(
                collect_provider_samples(
                    reference_provider,
                    config.prompt_suite,
                    batch_repetitions,
                    config.sampling.cooldown_ms,
                )
            )
            if batch_index + 1 < batch_count and config.anchor_calibration.inter_batch_cooldown_ms > 0:
                sleep(config.anchor_calibration.inter_batch_cooldown_ms / 1000)

    calibration = summarize_reference_anchor_calibration(
        config.prompt_suite,
        config.reference_provider,
        batch_samples,
        category_weights=config.calibration.category_weights,
        fingerprinting=config.fingerprinting,
        anchor_calibration=config.anchor_calibration,
    )
    payload = {
        "run_id": run_id,
        "created_at": utc_timestamp(),
        "config_name": config.name,
        "claimed_model": config.claimed_model,
        "reference_provider": config.reference_provider,
        "prompt_suite_name": config.prompt_suite.name,
        "provider_snapshot": asdict(provider_snapshot),
        "reference_anchor_calibration": calibration,
    }
    (output_dir / "anchor_calibration.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        f"# Reference Anchor Calibration: {config.name}",
        "",
        f"- Run ID: `{run_id}`",
        f"- Claimed model: `{config.claimed_model}`",
        f"- Reference provider: `{config.reference_provider}`",
        f"- Prompt suite: `{config.prompt_suite.name}`",
        f"- Batch count: `{calibration.get('batch_count', 0)}`",
        f"- Batch repetitions: `{batch_repetitions}`",
        f"- Available: `{calibration.get('available', False)}`",
        f"- Configured open-set threshold: `{float(calibration.get('configured_open_set_threshold', 0.0)):.3f}`",
    ]
    if calibration.get("available"):
        lines.extend(
            [
                f"- Pairwise similarity mean: `{float(calibration.get('pairwise_similarity_mean', 0.0)):.3f}`",
                f"- Pairwise similarity min: `{float(calibration.get('pairwise_similarity_min', 0.0)):.3f}`",
                f"- Pairwise similarity quantile: `{float(calibration.get('pairwise_similarity_quantile', 0.0)):.3f}`",
                f"- Suggested open-set threshold: `{float(calibration.get('suggested_open_set_similarity_threshold', 0.0)):.3f}`",
                f"- Open-set threshold to apply: `{float(calibration.get('open_set_threshold_to_apply', 0.0)):.3f}`",
            ]
        )
    else:
        reasons = calibration.get("reasons", [])
        if reasons:
            lines.append(f"- Reasons: {', '.join(str(item) for item in reasons)}")
    lines.extend(
        [
            "",
            "## Pairwise Batch Similarities",
            "",
            "| Left Batch | Right Batch | Weighted Similarity |",
            "| --- | --- | ---: |",
        ]
    )
    for pair in calibration.get("pairwise_batch_similarities", []):
        lines.append(
            f"| `{pair['left_batch']}` | `{pair['right_batch']}` | `{float(pair['weighted_similarity']):.3f}` |"
        )
    lines.extend(
        [
            "",
            "## Batch Stats",
            "",
            "| Batch | Total Samples | Successful Samples | Successful Cases | Failure Rate |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for batch in calibration.get("batches", []):
        lines.append(
            f"| `{batch['batch_id']}` | `{batch['total_samples']}` | `{batch['successful_sample_count']}` | "
            f"`{batch['successful_case_count']}` | `{float(batch['failure_rate']):.3f}` |"
        )
    (output_dir / "anchor_calibration.md").write_text("\n".join(lines), encoding="utf-8")
    return payload, output_dir


def inspect_providers(config_path: str | Path) -> dict[str, object]:
    config = load_audit_config(config_path)
    snapshots = {}
    with ExitStack() as stack:
        provider_names = [config.reference_provider, *config.negative_controls, *config.target_providers]
        seen = []
        for provider_name in provider_names:
            if provider_name in seen:
                continue
            seen.append(provider_name)
            provider = stack.enter_context(build_provider(config, provider_name))
            snapshots[provider_name] = provider.snapshot()
    return {
        "config": config.name,
        "claimed_model": config.claimed_model,
        "calibration": {
            "min_reference_samples": config.calibration.min_reference_samples,
            "min_calibrated_cases": config.calibration.min_calibrated_cases,
        },
        "providers": {name: asdict(snapshot) for name, snapshot in snapshots.items()},
    }


def rebuild_markdown(run_dir: str | Path) -> Path:
    run_path = Path(run_dir) / "run.json"
    with run_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    run = AuditRun(
        run_id=payload["run_id"],
        created_at=payload["created_at"],
        config_name=payload["config_name"],
        claimed_model=payload["claimed_model"],
        reference_provider=payload["reference_provider"],
        target_providers=payload.get("target_providers", []),
        prompt_suite_name=payload["prompt_suite_name"],
        reference_calibration=payload.get("reference_calibration", {}),
        provider_snapshots={
            name: ProviderSnapshot(**snapshot)
            for name, snapshot in payload.get("provider_snapshots", {}).items()
        },
        samples=[SampleResult(**sample) for sample in payload.get("samples", [])],
        analyses=[
            TargetAnalysis(
                provider=analysis["provider"],
                role=analysis["role"],
                metadata=analysis.get("metadata", {}),
                aggregate=analysis.get("aggregate", {}),
                verdict=analysis.get("verdict", {}),
                negative_control_comparison=analysis.get("negative_control_comparison", {}),
                cases=[CaseAnalysis(**case) for case in analysis.get("cases", [])],
                fingerprint=analysis.get("fingerprint", {}),
            )
            for analysis in payload.get("analyses", [])
        ],
    )
    report_path = Path(run_dir) / "report.md"
    report_path.write_text(render_markdown_report(run), encoding="utf-8")
    return report_path
