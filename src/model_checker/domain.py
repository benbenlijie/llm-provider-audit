from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RouterConfig:
    root: Path
    env_file: Path
    node_bin: str | None
    base_port: int
    startup_timeout_sec: int


@dataclass(slots=True)
class SamplingConfig:
    repetitions: int
    max_output_tokens: int
    timeout_sec: int
    cooldown_ms: int


@dataclass(slots=True)
class ScoringConfig:
    likely_match_similarity_ratio: float
    suspicious_similarity_ratio: float
    max_failure_rate: float
    max_json_pass_delta: float
    min_weighted_tail_probability: float
    severe_weighted_tail_probability: float
    outlier_case_pvalue_threshold: float
    max_outlier_case_count: int
    min_negative_control_margin: float


@dataclass(slots=True)
class CalibrationConfig:
    min_reference_samples: int
    min_calibrated_cases: int
    category_weights: dict[str, float]


@dataclass(slots=True)
class AnchorCalibrationConfig:
    enabled: bool
    batch_count: int
    batch_repetitions: int | None
    inter_batch_cooldown_ms: int
    similarity_quantile: float
    threshold_margin: float


@dataclass(slots=True)
class FingerprintConfig:
    enabled: bool
    open_set_min_anchor_similarity: float
    min_reference_margin: float
    reference_margin_scale: float


@dataclass(slots=True)
class ProviderConfig:
    name: str
    kind: str
    enabled: bool = True
    trust_env: bool = True
    router_group: str | None = None
    model_override: str | None = None
    fallback_provider_chain: list[str] = field(default_factory=list)
    base_url: str | None = None
    api_key_env: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class PromptCase:
    case_id: str
    category: str
    prompt: str
    expectations: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    discriminator_type: str | None = None
    notes: str | None = None
    turns: list[dict[str, str]] = field(default_factory=list)


@dataclass(slots=True)
class PromptSuite:
    name: str
    cases: list[PromptCase]


@dataclass(slots=True)
class AuditConfig:
    config_path: Path
    name: str
    claimed_model: str
    reference_provider: str
    target_providers: list[str]
    negative_controls: list[str]
    prompt_suite_path: Path
    report_dir: Path
    router: RouterConfig
    sampling: SamplingConfig
    scoring: ScoringConfig
    calibration: CalibrationConfig
    anchor_calibration: AnchorCalibrationConfig
    fingerprinting: FingerprintConfig
    providers: dict[str, ProviderConfig]
    prompt_suite: PromptSuite


@dataclass(slots=True)
class ProviderSnapshot:
    provider: str
    kind: str
    requested_model: str
    base_url: str
    health: dict[str, Any]
    models: dict[str, Any]


@dataclass(slots=True)
class SampleResult:
    provider: str
    case_id: str
    attempt: int
    success: bool
    text: str
    normalized_text: str
    latency_ms: float
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CaseAnalysis:
    case_id: str
    category: str
    reference_outputs: list[str]
    target_outputs: list[str]
    reference_sample_count: int
    target_sample_count: int
    reference_self_similarity: float
    reference_baseline_similarity: float | None
    cross_similarity: float
    relative_similarity: float | None
    empirical_tail_probability: float | None
    exact_match_rate: float
    reference_json_pass_rate: float | None
    target_json_pass_rate: float | None
    failure_rate: float
    calibrated: bool
    reference_expectation_pass_rate: float | None = None
    target_expectation_pass_rate: float | None = None
    discriminator_type: str | None = None
    tags: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass(slots=True)
class TargetAnalysis:
    provider: str
    role: str
    metadata: dict[str, Any]
    aggregate: dict[str, Any]
    verdict: dict[str, Any]
    negative_control_comparison: dict[str, Any]
    cases: list[CaseAnalysis]
    fingerprint: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AuditRun:
    run_id: str
    created_at: str
    config_name: str
    claimed_model: str
    reference_provider: str
    target_providers: list[str]
    prompt_suite_name: str
    reference_calibration: dict[str, Any]
    provider_snapshots: dict[str, ProviderSnapshot]
    samples: list[SampleResult]
    analyses: list[TargetAnalysis]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
