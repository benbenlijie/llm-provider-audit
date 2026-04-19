from __future__ import annotations

import json
from pathlib import Path

from ..domain import AuditRun


def write_json_report(run: AuditRun, output_dir: Path) -> Path:
    path = output_dir / "run.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(run.to_dict(), handle, indent=2, ensure_ascii=False)
    return path
