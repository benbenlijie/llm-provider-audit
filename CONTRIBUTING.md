# Contributing

## Development Setup

```bash
uv sync
```

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

## Pull Requests

- Keep changes scoped.
- Add or update tests when behavior changes.
- Preserve the CLI-first workflow unless there is a clear reason to introduce a new surface area.
- Use the GitHub issue and pull request templates where applicable.
- Sanitize all config snippets and screenshots before submitting them publicly.
