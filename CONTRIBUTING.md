# Contributing

## Development Setup

```bash
uv sync
python3 -m py_compile $(find "src" -name '*.py' | sort) $(find "tests" -name '*.py' | sort)
uv run python -m unittest discover -s "tests" -v
```

If you are adding or changing public audit templates, run at least one CLI smoke command against a sanitized local config before opening a PR.

## Test Commands

```bash
python3 -m py_compile $(find "src" -name '*.py' | sort) $(find "tests" -name '*.py' | sort)
uv run python -m unittest discover -s "tests" -v
```

## Configuration Hygiene

- Public templates live under `configs/audits/`.
- Private, machine-specific configs belong under `configs/local/`.
- Do not commit `.env`, `configs/local/`, or generated reports under `artifacts/runs/` and `artifacts/anchor-calibrations/`.
- When adding a new provider, prefer adding a sanitized public template first, then copy it locally for real credentials and endpoints.
- Never paste real API keys, bearer tokens, account identifiers, private base URLs, or organization-specific headers into issues, pull requests, examples, screenshots, or generated Markdown reports.
- If a report excerpt is useful for debugging, redact provider names and secrets unless the provider and endpoint are intentionally public.

## Good First Contributions

- Add sanitized prompt cases to `configs/prompt-suites/`.
- Improve comments and placeholder guidance in `configs/audits/*.yaml`.
- Add tests for verdict thresholds, report fields, and secret-redaction behavior.
- Improve docs for running local audits safely.
- Add small CLI ergonomics improvements that preserve the CLI-first workflow.

## Pull Requests

- Keep changes scoped.
- Add or update tests when behavior changes.
- Preserve the CLI-first workflow unless there is a clear reason to introduce a new surface area.
- Use the GitHub issue and pull request templates where applicable.
- Sanitize all config snippets and screenshots before submitting them publicly.
