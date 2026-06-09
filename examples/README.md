# Examples

This directory contains sanitized example artifacts that demonstrate the shape of `llm-provider-audit` outputs without requiring real provider credentials.

## Reports

- [`reports/likely-match.md`](reports/likely-match.md): a target provider that stays within the expected reference variance.
- [`reports/suspicious-mismatch.md`](reports/suspicious-mismatch.md): a target provider that shows degraded similarity and fingerprint warnings.

## Fixtures

- [`fixtures/likely-match-run.json`](fixtures/likely-match-run.json): compact fixture matching the likely-match report.
- [`fixtures/suspicious-mismatch-run.json`](fixtures/suspicious-mismatch-run.json): compact fixture matching the suspicious-mismatch report.

## Safety notes

All provider names, model names, endpoints, prompts, and outputs here are intentionally synthetic. Do not infer anything about a real provider from these examples.

When sharing your own reports publicly, redact:

- API keys and bearer tokens
- private base URLs and account identifiers
- organization-specific headers
- local filesystem paths
- proprietary prompts or test cases
