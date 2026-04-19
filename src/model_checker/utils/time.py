from __future__ import annotations

from datetime import UTC, datetime


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def file_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
