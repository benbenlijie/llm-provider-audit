from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .domain import (
    AnchorCalibrationConfig,
    AuditConfig,
    CalibrationConfig,
    FingerprintConfig,
    PromptCase,
    PromptSuite,
    ProviderConfig,
    RouterConfig,
    SamplingConfig,
    ScoringConfig,
)


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand_env_string(value: str, *, source: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        default = match.group(2)
        env_value = os.environ.get(env_name)
        if env_value is not None and env_value != "":
            return env_value
        if default is not None:
            return default
        raise ValueError(f"Missing environment variable '{env_name}' while loading {source}")

    return _ENV_PATTERN.sub(replace, value)


def _expand_env_data(value: Any, *, source: Path) -> Any:
    if isinstance(value, dict):
        return {key: _expand_env_data(item, source=source) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand_env_data(item, source=source) for item in value]
    if isinstance(value, str):
        return _expand_env_string(value, source=source)
    return value


def _load_yaml(path: Path, *, expand_env: bool = False) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    if expand_env:
        expanded = _expand_env_data(data, source=path)
        if not isinstance(expanded, dict):
            raise ValueError(f"Expanded YAML root must remain a mapping: {path}")
        return expanded
    return data


def _resolve_path(base: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (base / path).resolve()


def load_prompt_suite(path: Path) -> PromptSuite:
    data = _load_yaml(path)
    cases = []
    for item in data.get("cases", []):
        turns = []
        for turn in item.get("turns", []):
            if not isinstance(turn, dict):
                raise ValueError(f"Prompt turns must be mappings: {path}")
            turns.append({str(key): str(value) for key, value in turn.items()})
        cases.append(
            PromptCase(
                case_id=item["id"],
                category=item["category"],
                prompt=item["prompt"],
                expectations=dict(item.get("expectations", {})),
                tags=[str(tag) for tag in item.get("tags", [])],
                discriminator_type=(
                    str(item["discriminator_type"])
                    if item.get("discriminator_type") is not None
                    else None
                ),
                notes=str(item["notes"]) if item.get("notes") is not None else None,
                turns=turns,
            )
        )
    return PromptSuite(name=data.get("name", path.stem), cases=cases)


def load_audit_config(path: str | Path) -> AuditConfig:
    config_path = Path(path).resolve()
    base_dir = config_path.parent
    data = _load_yaml(config_path, expand_env=True)

    prompt_suite_path = _resolve_path(base_dir, data["prompt_suite"])
    report_dir = _resolve_path(base_dir, data["report_dir"])

    router_data = data["router"]
    router = RouterConfig(
        root=_resolve_path(base_dir, router_data["root"]),
        env_file=_resolve_path(base_dir, router_data["env_file"]),
        node_bin=router_data.get("node_bin"),
        base_port=int(router_data.get("base_port", 19090)),
        startup_timeout_sec=int(router_data.get("startup_timeout_sec", 20)),
    )

    sampling_data = data.get("sampling", {})
    sampling = SamplingConfig(
        repetitions=int(sampling_data.get("repetitions", 2)),
        max_output_tokens=int(sampling_data.get("max_output_tokens", 256)),
        timeout_sec=int(sampling_data.get("timeout_sec", 90)),
        cooldown_ms=int(sampling_data.get("cooldown_ms", 0)),
    )

    scoring_data = data.get("scoring", {})
    scoring = ScoringConfig(
        likely_match_similarity_ratio=float(scoring_data.get("likely_match_similarity_ratio", 0.9)),
        suspicious_similarity_ratio=float(scoring_data.get("suspicious_similarity_ratio", 0.75)),
        max_failure_rate=float(scoring_data.get("max_failure_rate", 0.3)),
        max_json_pass_delta=float(scoring_data.get("max_json_pass_delta", 0.34)),
        min_weighted_tail_probability=float(scoring_data.get("min_weighted_tail_probability", 0.35)),
        severe_weighted_tail_probability=float(scoring_data.get("severe_weighted_tail_probability", 0.12)),
        outlier_case_pvalue_threshold=float(scoring_data.get("outlier_case_pvalue_threshold", 0.1)),
        max_outlier_case_count=int(scoring_data.get("max_outlier_case_count", 2)),
        min_negative_control_margin=float(scoring_data.get("min_negative_control_margin", 0.05)),
    )

    calibration_data = data.get("calibration", {})
    calibration = CalibrationConfig(
        min_reference_samples=int(calibration_data.get("min_reference_samples", 2)),
        min_calibrated_cases=int(calibration_data.get("min_calibrated_cases", 4)),
        category_weights={
            str(key): float(value)
            for key, value in calibration_data.get(
                "category_weights",
                {
                    "exact": 1.5,
                    "strict_json": 1.5,
                    "structure": 1.0,
                    "reasoning": 0.75,
                    "safety": 0.75,
                },
            ).items()
        },
    )

    anchor_calibration_data = data.get("anchor_calibration", {})
    raw_batch_repetitions = anchor_calibration_data.get("batch_repetitions")
    anchor_calibration = AnchorCalibrationConfig(
        enabled=bool(anchor_calibration_data.get("enabled", False)),
        batch_count=int(anchor_calibration_data.get("batch_count", 3)),
        batch_repetitions=(int(raw_batch_repetitions) if raw_batch_repetitions is not None else None),
        inter_batch_cooldown_ms=int(anchor_calibration_data.get("inter_batch_cooldown_ms", 0)),
        similarity_quantile=float(anchor_calibration_data.get("similarity_quantile", 0.1)),
        threshold_margin=float(anchor_calibration_data.get("threshold_margin", 0.02)),
    )

    fingerprinting_data = data.get("fingerprinting", {})
    fingerprinting = FingerprintConfig(
        enabled=bool(fingerprinting_data.get("enabled", True)),
        open_set_min_anchor_similarity=float(fingerprinting_data.get("open_set_min_anchor_similarity", 0.4)),
        min_reference_margin=float(fingerprinting_data.get("min_reference_margin", 0.05)),
        reference_margin_scale=float(fingerprinting_data.get("reference_margin_scale", 0.2)),
    )

    providers: dict[str, ProviderConfig] = {}
    for name, provider_data in data.get("providers", {}).items():
        providers[name] = ProviderConfig(
            name=name,
            kind=provider_data["kind"],
            enabled=bool(provider_data.get("enabled", True)),
            trust_env=bool(provider_data.get("trust_env", True)),
            router_group=provider_data.get("router_group"),
            model_override=provider_data.get("model_override"),
            fallback_provider_chain=list(provider_data.get("fallback_provider_chain", [])),
            base_url=provider_data.get("base_url"),
            api_key_env=provider_data.get("api_key_env"),
            headers=dict(provider_data.get("headers", {})),
        )

    prompt_suite = load_prompt_suite(prompt_suite_path)

    return AuditConfig(
        config_path=config_path,
        name=data["name"],
        claimed_model=data["claimed_model"],
        reference_provider=data["reference_provider"],
        target_providers=list(data.get("target_providers", [])),
        negative_controls=list(data.get("negative_controls", [])),
        prompt_suite_path=prompt_suite_path,
        report_dir=report_dir,
        router=router,
        sampling=sampling,
        scoring=scoring,
        calibration=calibration,
        anchor_calibration=anchor_calibration,
        fingerprinting=fingerprinting,
        providers=providers,
        prompt_suite=prompt_suite,
    )
