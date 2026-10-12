from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import healer

from .demo import run_demo
from .errors import HealerError
from .report import build_report, write_report
from .sponsors import entire_status


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="healer", description="Trace-driven QA for AI agents")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument(
        "--dry-run", action="store_true", help="Forbid mutation (the default for scans)"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Check tracing and trace-read capabilities")
    scan = sub.add_parser("scan", help="Scan recent Neatlogs or local traces")
    scan.add_argument("--since", default="24h")
    scan.add_argument("--tag")
    scan.add_argument("--trace-id")
    scan.add_argument("--limit", type=int, default=100)

    doctor = sub.add_parser("doctor", help="Join trace findings with local repository context")
    doctor.add_argument("--repo", default=".")
    doctor.add_argument("--since", default="24h")
    doctor.add_argument("--app-id")
    doctor.add_argument("--session-id")
    doctor.add_argument("--limit", type=int, default=100)

    report = sub.add_parser("report", help="Write a report from a fresh scan")
    report.add_argument("--since", default="24h")
    report.add_argument("--tag")
    report.add_argument("--output", default="evidence/healer-report.json")

    demo = sub.add_parser("demo", help="Run the deterministic three-minute demo")
    demo.add_argument("--output-dir", default="evidence/demo")

    serve = sub.add_parser("serve", help="Serve the read-only HTTP API")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    serve.add_argument(
        "--allow-unauthenticated",
        action="store_true",
        help="Allow API access without HEALER_SERVER_TOKEN (trusted networks only)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "serve":
            from .server import serve

            serve(
                host=args.host,
                port=args.port,
                allow_unauthenticated=args.allow_unauthenticated,
            )
            return 0
        if args.command == "demo":
            payload = run_demo(args.output_dir)
        else:
            capability = healer.init()
            if args.command == "status":
                payload = {"neatlogs": capability.to_dict(), "entire": entire_status()}
            elif args.command == "scan":
                findings = healer.scan(
                    since=args.since,
                    tag=args.tag,
                    trace_id=args.trace_id,
                    limit=args.limit,
                )
                payload = {
                    "count": len(findings),
                    "findings": [finding.to_dict() for finding in findings],
                }
            elif args.command == "doctor":
                payload = healer.doctor(
                    repo_path=args.repo,
                    since=args.since,
                    app_id=args.app_id,
                    session_id=args.session_id,
                    limit=args.limit,
                )
            elif args.command == "report":
                findings = healer.scan(since=args.since, tag=args.tag)
                report = build_report(findings)
                path = write_report(report, args.output)
                payload = {"path": str(path), "finding_count": len(findings)}
            else:  # pragma: no cover - argparse guarantees a command
                raise AssertionError(args.command)
    except HealerError as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "type": type(exc).__name__}))
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _human(payload)
    return 0


def _human(payload: dict[str, Any]) -> None:
    if "findings" in payload and isinstance(payload["findings"], list):
        print(f"{payload.get('count', len(payload['findings']))} finding(s)")
        for finding in payload["findings"]:
            print(f"[{finding['severity']}] {finding['reason']} ({finding['trace_id']})")
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
