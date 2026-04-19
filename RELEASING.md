# Releasing / Publishing Checklist

Use this checklist before the first public GitHub release.

## Repository Hygiene

- Confirm `.gitignore` is active.
- Confirm `.env`, `configs/local/`, `.venv/`, and generated `artifacts/` are untracked.
- Run a final secret scan on the repository history if this code previously lived in a private workspace.

## Metadata

- Confirm `pyproject.toml` URLs point to the public repository.
- Review `LICENSE` ownership and year.
- Review `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, and `CODE_OF_CONDUCT.md`.

## GitHub Repository Settings

- Suggested repository description:
  - `CLI framework for auditing LLM providers and detecting model substitution.`
- Suggested topics:
  - `llm`
  - `provider-audit`
  - `model-audit`
  - `model-substitution`
  - `openai-compatible`
  - `model-fingerprinting`
  - `model-routing`
  - `prompt-testing`
  - `llm-evaluation`
  - `ai-infra`
- Suggested first release title:
  - `v0.1.0 - Initial public release`
- Suggested first release notes source:
  - `docs/releases/v0.1.0.md`

## Technical Verification

```bash
uv sync
python3 -m py_compile $(find "src" -name '*.py' | sort) $(find "tests" -name '*.py' | sort)
uv run python -m unittest discover -s "tests" -v
```

## Public Configuration Review

- Public templates under `configs/audits/` should contain only placeholders or environment-variable-driven values.
- Real local configs should remain under `configs/local/`.
- If you introduce a new provider, add a sanitized public template first.
- Prefer generic public template names over provider-branded names for homepage-facing examples.

## Suggested First Push Flow

```bash
git init
git add .
git status
git remote add origin <your-github-repo-url>
git commit -m "Initial public release"
git push -u origin main
```

Review `git status` carefully before the first commit.
