from __future__ import annotations

import argparse
import json
from pathlib import Path

from .orchestration import (
    inspect_providers,
    rebuild_markdown,
    run_audit,
    run_reference_anchor_calibration,
    run_reference_calibration,
)
from .utils.dotenv import load_default_env


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="llm-provider-audit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect-router")
    inspect_parser.add_argument("--config", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", required=True)
    run_parser.add_argument("--reference-anchor-calibration", required=False)

    calibrate_parser = subparsers.add_parser("calibrate")
    calibrate_parser.add_argument("--config", required=True)

    anchor_calibrate_parser = subparsers.add_parser("anchor-calibrate")
    anchor_calibrate_parser.add_argument("--config", required=True)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--run", required=True)
    return parser


def main() -> int:
    load_default_env()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "inspect-router":
        payload = inspect_providers(args.config)
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.command == "run":
        run, output_dir = run_audit(
            args.config,
            reference_anchor_calibration_path=args.reference_anchor_calibration,
        )
        summary = {
            "run_id": run.run_id,
            "output_dir": str(output_dir),
            "claimed_model": run.claimed_model,
            "reference_provider": run.reference_provider,
            "targets": [
                {
                    "provider": analysis.provider,
                    "verdict": analysis.verdict["label"],
                    "cross_similarity_ratio": analysis.aggregate["cross_similarity_ratio"],
                    "weighted_tail_probability": analysis.aggregate.get("weighted_tail_probability", 0.0),
                    "fingerprint_label": analysis.fingerprint.get("label"),
                    "fingerprint_nearest_anchor": analysis.fingerprint.get("nearest_anchor_provider"),
                    "fingerprint_reference_margin": analysis.fingerprint.get("reference_margin_vs_best_alternative"),
                    "fingerprint_margin_threshold": analysis.fingerprint.get("calibrated_reference_margin_threshold"),
                    "fingerprint_open_set_threshold": analysis.fingerprint.get("open_set_similarity_threshold_used"),
                    "fingerprint_open_set_threshold_source": analysis.fingerprint.get("open_set_threshold_source"),
                }
                for analysis in run.analyses
                if analysis.role == "target"
            ],
            "negative_controls": [
                {
                    "provider": analysis.provider,
                    "verdict": analysis.verdict["label"],
                    "cross_similarity_ratio": analysis.aggregate["cross_similarity_ratio"],
                    "fingerprint_label": analysis.fingerprint.get("label"),
                    "fingerprint_nearest_anchor": analysis.fingerprint.get("nearest_anchor_provider"),
                }
                for analysis in run.analyses
                if analysis.role == "negative_control"
            ],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    if args.command == "calibrate":
        payload, output_dir = run_reference_calibration(args.config)
        summary = {
            "run_id": payload["run_id"],
            "output_dir": str(output_dir),
            "claimed_model": payload["claimed_model"],
            "reference_provider": payload["reference_provider"],
            "calibrated_case_count": payload["reference_calibration"]["calibrated_case_count"],
            "uncalibrated_case_count": payload["reference_calibration"]["uncalibrated_case_count"],
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    if args.command == "anchor-calibrate":
        payload, output_dir = run_reference_anchor_calibration(args.config)
        calibration = payload["reference_anchor_calibration"]
        summary = {
            "run_id": payload["run_id"],
            "output_dir": str(output_dir),
            "claimed_model": payload["claimed_model"],
            "reference_provider": payload["reference_provider"],
            "prompt_suite_name": payload["prompt_suite_name"],
            "available": calibration.get("available", False),
            "pairwise_similarity_quantile": calibration.get("pairwise_similarity_quantile"),
            "suggested_open_set_similarity_threshold": calibration.get("suggested_open_set_similarity_threshold"),
            "open_set_threshold_to_apply": calibration.get("open_set_threshold_to_apply"),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    if args.command == "report":
        path = rebuild_markdown(Path(args.run))
        print(str(path))
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
