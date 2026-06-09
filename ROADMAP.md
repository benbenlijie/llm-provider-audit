# Roadmap

This roadmap tracks the near-term maintenance plan for `llm-provider-audit`. The canonical implementation tasks are kept as GitHub issues so contributors can discuss and pick up scoped work.

## 1. Provider fingerprinting and regression suites

- Expand behavioral probes for OpenAI-compatible providers.
- Add stronger negative controls for low-tier, fallback, and unrelated model families.
- Improve `open_set` threshold calibration so reports can distinguish normal randomness from suspicious model substitution.

## 2. CI-friendly drift detection

- Add commands and examples for scheduled provider audits.
- Support stable JSON output that can be compared across runs.
- Make it easy to fail or warn in CI when a provider drifts beyond configured thresholds.

## 3. Security and configuration hygiene

- Harden redaction of API keys, custom headers, local paths, and private endpoints.
- Add tests that ensure generated reports never include secrets from `.env` or local configs.
- Keep public templates sanitized and reproducible.

## 4. Public examples and contributor onboarding

- Publish sanitized example audit reports.
- Add minimal fixtures for contributors who do not have access to paid providers.
- Improve `good first issue` tasks around templates, prompt suites, docs, and report fields.

## 5. Reporting and history

- Add lightweight local history storage for audit runs.
- Generate trend views for provider drift over time.
- Prepare a future Web report surface while keeping the CLI workflow first.

## Maintainer focus

The maintainer focus for the next six months is to make the project safer, more reproducible, and easier for other developers to run when evaluating OpenAI-compatible providers.
