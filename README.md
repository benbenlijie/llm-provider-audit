# LLM Provider Audit

[![CI](https://github.com/benbenlijie/llm-provider-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/benbenlijie/llm-provider-audit/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/benbenlijie/llm-provider-audit/blob/main/LICENSE)

[中文说明](README.zh-CN.md)

`llm-provider-audit` is a CLI-first framework for auditing OpenAI-compatible LLM providers and detecting model substitution, degraded routing, fallback contamination, and behavior drift.

It is not a general benchmark. It is built to answer a narrower operational question:

> Is this provider actually returning behavior close to the model it claims to serve?

## Why this matters

OpenAI-compatible endpoints make it easy for developers to switch providers, but they also make provider behavior harder to verify. A provider may silently route traffic to a cheaper model, fall back to a different model under load, change routing policies over time, or expose inconsistent behavior across regions and accounts.

This project gives developers and maintainers a reproducible way to collect evidence before trusting a provider in production:

- compare a target provider against a reference provider and negative controls
- estimate normal reference variance before flagging mismatches
- keep sanitized JSON/Markdown audit reports for regressions and reviews
- support periodic checks for behavior drift in OpenAI-compatible routing

## Use cases

- Audit third-party gateways, proxies, and model-routing providers for possible model substitution.
- Compare whether multiple providers are genuinely close to the same reference model.
- Track provider behavior drift over time.
- Produce structured evidence for scheduled checks, alerts, or future web reporting.
- Run a safety and reliability preflight before integrating a new provider.

## Methodology

- **Reference calibration:** estimate the reference provider's natural variance before treating differences as suspicious.
- **Negative controls:** compare against known lower-tier or alternative models so a target is not considered trustworthy merely because it is somewhat close to the reference.
- **Fingerprinting:** use nearest-anchor matching and open-set thresholds to identify whether a target falls outside known distributions.
- **JSON + Markdown reports:** preserve aggregate scores, per-case metrics, representative excerpts, and final verdicts for review.

## Quick start

```bash
uv sync
cp ".env.example" ".env"
mkdir -p "configs/local"
cp "configs/audits/openai-compatible-template.yaml" "configs/local/target-provider.yaml"
uv run llm-provider-audit inspect-router --config "configs/local/target-provider.yaml"
uv run llm-provider-audit run --config "configs/local/target-provider.yaml"
```

Fill these values in `.env` first:

- `MODEL_CHECKER_ROUTER_ROOT`
- `MODEL_CHECKER_ROUTER_ENV_FILE`
- `MODEL_CHECKER_TARGET_BASE_URL`
- `MODEL_CHECKER_TARGET_API_KEY`

The CLI automatically searches for `.env` from the current directory upward and does not override environment variables that are already set.

If you are not running commands from the repository root, or if you want the current shell to explicitly load variables, run:

```bash
set -a
. ".env"
set +a
```

Before a public release, also review the checklist in [`RELEASING.md`](RELEASING.md).

## Common commands

Inspect provider health and model listing from a config:

```bash
uv run llm-provider-audit inspect-router --config "configs/local/target-provider.yaml"
```

Run reference calibration:

```bash
uv run llm-provider-audit calibrate --config "configs/audits/openai-compatible-template.yaml"
```

Run reference anchor calibration:

```bash
uv run llm-provider-audit anchor-calibrate --config "configs/audits/openai-compatible-deep-template.yaml"
```

Run a full audit:

```bash
uv run llm-provider-audit run --config "configs/local/target-provider.yaml"
```

Run a deep audit using an existing reference anchor calibration to adjust the open-set threshold:

```bash
uv run llm-provider-audit run \
  --config "configs/audits/openai-compatible-deep-template.yaml" \
  --reference-anchor-calibration "artifacts/anchor-calibrations/<run-id>/anchor_calibration.json"
```

Rebuild a Markdown report from an existing `run.json`:

```bash
uv run llm-provider-audit report --run "artifacts/runs/<run-id>"
```

## Configuration conventions

- `configs/audits/*.yaml` contains public, commit-safe template configs.
- `configs/local/` is for private machine-specific configs and is ignored by git.
- Public templates should contain only placeholders or environment variables, never real endpoints, API keys, account IDs, or local paths.
- The repository keeps a small number of historical example templates for research reproducibility, but the homepage defaults to generic templates.

## Verdict labels

- `likely_match`: the target provider is close enough to the reference provider.
- `suspicious_mismatch`: the target deviates from the reference, but the evidence is not yet decisive.
- `strong_mismatch`: multiple metrics strongly deviate, suggesting possible model substitution or degradation.
- `insufficient_evidence`: sample count or stability is insufficient for a reliable conclusion.

Markdown reports include:

- aggregate metrics
- per-case similarity, tail probability, and failure rate
- representative sample excerpts
- the target provider's margin against the best negative control
- the fingerprint open-set threshold and its source

## Examples

Sanitized reports and public JSON fixtures are available under [`examples/`](examples/):

- [`examples/reports/likely-match.md`](examples/reports/likely-match.md)
- [`examples/reports/suspicious-mismatch.md`](examples/reports/suspicious-mismatch.md)
- [`examples/fixtures/likely-match-run.json`](examples/fixtures/likely-match-run.json)
- [`examples/fixtures/suspicious-mismatch-run.json`](examples/fixtures/suspicious-mismatch-run.json)

All example providers, endpoints, prompts, outputs, and model names are synthetic.

## Roadmap

Current roadmap items are tracked as public GitHub issues so contributors can pick up scoped work:

- Provider fingerprinting suite for stronger mismatch detection
- CI-friendly drift checks for scheduled provider audits
- Sanitized example reports and public audit fixtures
- Security hardening around API keys, logs, configs, and generated artifacts
- Contributor-friendly audit templates for common OpenAI-compatible providers
- Lightweight history storage and trend visualization

## How Codex can help this project

This project has several maintenance areas where agentic coding support is useful:

- expanding unit and regression tests for statistical verdict logic
- reviewing security-sensitive paths that touch API keys, headers, logs, and generated reports
- generating sanitized provider templates without leaking real endpoints or credentials
- improving CLI ergonomics and documentation examples
- building reproducible fixtures for provider behavior drift and model-substitution detection
- maintaining report generation across JSON, Markdown, and future web views

A scoped plan for Codex-friendly open-source tasks is available in [`docs/codex-open-source-plan.md`](docs/codex-open-source-plan.md).

## Contributing

Contributions are welcome. Good first areas include:

- adding sanitized prompt cases to `configs/prompt-suites/`
- improving public provider templates under `configs/audits/`
- adding tests around verdict thresholds and report fields
- improving docs for local setup and safe configuration hygiene

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development setup and pull request expectations.

## Security and open-source hygiene

Do not commit:

- `.env`
- `configs/local/`
- `artifacts/runs/`
- `artifacts/anchor-calibrations/`
- real provider endpoints, API keys, account IDs, private headers, local paths, or proprietary prompts

If you add a new provider, write a public template first, then copy it into `configs/local/` for real local usage. If a provider requires extra headers or custom authentication, keep the public template placeholder-based.
