from __future__ import annotations

import json
import re
from typing import Any


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _count_sentences(text: str) -> int:
    segments = [segment.strip() for segment in re.split(r"[.!?]+", text) if segment.strip()]
    return len(segments)


def _count_bullets(text: str) -> int:
    count = 0
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^([-*+]\s+|\d+\.\s+)", stripped):
            count += 1
    return count


def json_passes_expectations(text: str, expectations: dict[str, Any]) -> bool | None:
    expected_keys = expectations.get("json_keys")
    if not expected_keys:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    return sorted(parsed.keys()) == sorted(expected_keys)


def evaluate_expectations(text: str, expectations: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    json_result = json_passes_expectations(text, expectations)
    if json_result is not None:
        checks["json_keys"] = json_result

    normalized_text = normalize_text(text).lower()

    must_include = [str(item).lower() for item in expectations.get("must_include_substrings", [])]
    if must_include:
        checks["must_include_substrings"] = all(item in normalized_text for item in must_include)

    must_exclude = [str(item).lower() for item in expectations.get("must_exclude_substrings", [])]
    if must_exclude:
        checks["must_exclude_substrings"] = all(item not in normalized_text for item in must_exclude)

    max_sentences = expectations.get("max_sentences")
    if max_sentences is not None:
        checks["max_sentences"] = _count_sentences(text) <= int(max_sentences)

    exact_bullet_count = expectations.get("exact_bullet_count")
    if exact_bullet_count is not None:
        checks["exact_bullet_count"] = _count_bullets(text) == int(exact_bullet_count)

    return checks


def text_passes_expectations(text: str, expectations: dict[str, Any]) -> bool | None:
    checks = evaluate_expectations(text, expectations)
    if not checks:
        return None
    return all(checks.values())
