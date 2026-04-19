# Security Policy

## Supported Versions

The project is still in an early stage.
Security fixes are applied on the latest main branch only.

## Reporting a Vulnerability

- Do not open a public GitHub issue for suspected credential leaks or security vulnerabilities.
- Report the issue privately to the project maintainer.
- Include:
  - a concise description
  - affected files or commands
  - reproduction steps
  - whether any secrets may already be exposed

## Scope

The most likely security risks in this repository are:

- accidentally committed credentials
- unsafe public configuration templates
- generated artifacts containing sensitive endpoints or metadata

Before opening a pull request, verify that:

- `.env` and `configs/local/` are not tracked
- generated files under `artifacts/` are not tracked
- public templates under `configs/audits/` do not contain private endpoints or local filesystem paths
