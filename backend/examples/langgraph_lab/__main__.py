"""Run the two LangGraph attack suites with local Specter traces."""

from __future__ import annotations

import json
from pathlib import Path

import healer
from healer.lab_runner import CATALOG, run_lab


def main() -> None:
    healer.init(local_log=Path(".healer/lab-runs.jsonl"))
    for example in CATALOG:
        report = run_lab(example)
        print(
            json.dumps(
                {
                    "example": example,
                    "before_passed": report["before_passed"],
                    "after_passed": report["after_passed"],
                    "case_count": report["case_count"],
                    "cases": [
                        {
                            "case": item["case"],
                            "before": item["before"]["passed"],
                            "after": item["after"]["passed"],
                            "trace_id": item["after"]["trace_id"],
                        }
                        for item in report["cases"]
                    ],
                    "provider_evidence": report["provider_evidence"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
