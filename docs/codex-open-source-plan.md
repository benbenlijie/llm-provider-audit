# Codex Open Source Plan

This document lists contributor-friendly areas where Codex or another coding agent can help improve `llm-provider-audit` without needing private provider credentials.

The goal is to keep agent tasks small, reviewable, and safe for an open-source repository that handles provider endpoints, headers, prompts, and generated audit artifacts.

## Principles

1. **No private credentials in prompts or fixtures.** Use placeholders such as `https://redacted.example/v1`, `EXAMPLE_API_KEY`, and synthetic model names.
2. **Prefer fixtures over live providers.** Agent tasks should run against local JSON fixtures and deterministic tests whenever possible.
3. **Keep public templates generic.** Provider-specific templates should use environment variables and comments, not real account metadata.
4. **Make verdict logic testable.** Changes to scoring, calibration, fingerprinting, or reporting should include unit or regression tests.
5. **Separate research from production paths.** Experimental scoring ideas should land behind explicit config fields or docs before becoming defaults.

## High-value Codex tasks

### 1. Regression tests for report rendering

**Why:** Markdown and JSON reports are the durable audit evidence. Small schema changes can silently break downstream review workflows.

**Suggested scope:**

- Load sanitized fixtures from `examples/fixtures/`.
- Rebuild Markdown reports into a temporary directory.
- Assert that key fields appear:
  - verdict label
  - weighted relative similarity
  - negative-control margin
  - fingerprint nearest anchor
  - representative sample excerpts

**Acceptance criteria:**

- Tests run with `uv run pytest`.
- Tests do not call any network endpoint.
- Tests do not depend on provider credentials.

### 2. Fixture schema validation

**Why:** Example artifacts are both documentation and regression inputs. A broken fixture makes onboarding harder.

**Suggested scope:**

- Add a lightweight fixture validation test for every `examples/fixtures/*.json` file.
- Verify required top-level fields such as `run_id`, `claimed_model`, `reference_provider`, `samples`, and `analyses`.
- Verify every analysis has `aggregate`, `verdict`, and `cases`.

**Acceptance criteria:**

- All current example fixtures pass.
- Invalid JSON fails with a clear test message.
- No new runtime dependency is required unless strongly justified.

### 3. Safer redaction utilities

**Why:** This project touches sensitive fields: base URLs, API keys, request headers, raw responses, and local paths.

**Suggested scope:**

- Add a small redaction helper for report/debug output.
- Cover common patterns:
  - bearer tokens
  - API key-looking values
  - `Authorization` headers
  - private base URLs
  - local home-directory paths
- Add tests for false positives and false negatives.

**Acceptance criteria:**

- Redaction is applied before writing public-facing diagnostics.
- Tests cover representative secrets without using real secrets.
- The implementation is conservative and easy to audit.

### 4. CI-friendly drift check mode

**Why:** Users may want scheduled checks that fail or warn when a provider drifts, but CI jobs need predictable exits and compact output.

**Suggested scope:**

- Add a documented CLI mode or option that emits a compact summary suitable for CI logs.
- Optionally support a configurable exit-code policy:
  - `0` for likely match / insufficient evidence
  - non-zero for suspicious or strong mismatch
- Document how to run it in GitHub Actions without storing artifacts publicly.

**Acceptance criteria:**

- The behavior is opt-in.
- Existing `run` behavior remains backward-compatible.
- Docs include secret-handling warnings for GitHub Actions.

### 5. Contributor templates for common providers

**Why:** New users need examples, but public templates must not leak private endpoints or account details.

**Suggested scope:**

- Add additional `configs/audits/*-template.yaml` files for common OpenAI-compatible patterns.
- Keep all values as placeholders or environment variables.
- Add comments explaining required variables and optional headers.

**Acceptance criteria:**

- Templates pass existing config loading tests or a new template smoke test.
- No private endpoint, account ID, or token appears in the files.
- README or docs link to the new templates.

## Suggested task prompt template

Use this template when delegating work to Codex:

```text
You are working in the llm-provider-audit repository.

Task:
<one scoped task from docs/codex-open-source-plan.md>

Constraints:
- Do not call live provider APIs.
- Do not add real credentials, endpoints, account IDs, or private prompts.
- Prefer sanitized fixtures under examples/fixtures/.
- Run uv run pytest before finishing.
- Summarize changed files, tests run, and any security-sensitive assumptions.
```

## Review checklist for agent-generated changes

Before merging Codex output, check:

- [ ] `git diff` contains no real credentials, private endpoints, local absolute paths, or proprietary prompts.
- [ ] Tests cover the changed behavior.
- [ ] `uv run pytest` passes locally or in CI.
- [ ] Public docs explain any new config fields or CLI behavior.
- [ ] New fixtures are synthetic and clearly labeled as examples.

## Not recommended for first Codex tasks

Avoid starting with these until the test surface is stronger:

- large scoring algorithm rewrites
- provider-specific live integration code
- automatic publishing of audit reports
- database migrations for historical runs
- web UI dashboards that require a new frontend stack

These are valuable later, but they create a wider review surface and more chances to leak environment-specific assumptions.
