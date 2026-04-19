from __future__ import annotations

import os
from pathlib import Path


def _parse_env_value(raw_value: str) -> str:
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(path: Path, *, overwrite: bool = False) -> bool:
    if not path.is_file():
        return False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        if not overwrite and key in os.environ:
            continue
        os.environ[key] = _parse_env_value(raw_value)
    return True


def load_default_env(start_dir: Path | None = None, *, filename: str = ".env", overwrite: bool = False) -> Path | None:
    current = (start_dir or Path.cwd()).resolve()
    search_roots = [current, *current.parents]
    for directory in search_roots:
        candidate = directory / filename
        if load_env_file(candidate, overwrite=overwrite):
            return candidate
    return None
