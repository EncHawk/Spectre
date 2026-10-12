"""Bounded static Python call graph for repository investigation.

Edges are possible calls inferred from syntax, never proof of a runtime call.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path


def build_code_graph(repo: Path) -> dict:
    root = repo.resolve()
    try:
        process = subprocess.run(
            ["git", "-c", f"safe.directory={root}", "ls-files", "--", "*.py"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "basis": "static Python calls; repository not indexed",
        }
    if process.returncode:
        return {
            "nodes": [],
            "edges": [],
            "node_count": 0,
            "edge_count": 0,
            "basis": "static Python calls; repository not indexed",
        }
    nodes: list[dict] = []
    pending: list[tuple[str, str, set[str]]] = []
    total_bytes = 0
    for relative in process.stdout.splitlines()[:500]:
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        size = path.stat().st_size
        if size > 1_000_000 or total_bytes + size > 20_000_000:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError):
            continue
        total_bytes += size

        def visit(body: list[ast.stmt], prefix: str = "", filename: str = relative) -> None:
            for item in body:
                if isinstance(item, ast.ClassDef):
                    visit(item.body, f"{prefix}{item.name}.", filename)
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbol = f"{prefix}{item.name}"
                    identifier = f"{filename}::{symbol}"
                    nodes.append(
                        {"id": identifier, "file": filename, "symbol": symbol, "line": item.lineno}
                    )
                    calls = {
                        call.func.id if isinstance(call.func, ast.Name) else call.func.attr
                        for call in ast.walk(item)
                        if isinstance(call, ast.Call)
                        and isinstance(call.func, (ast.Name, ast.Attribute))
                    }
                    pending.append((identifier, filename, calls))

        visit(tree.body)
    by_name: dict[str, list[dict]] = {}
    for node in nodes:
        by_name.setdefault(node["symbol"].rsplit(".", 1)[-1], []).append(node)
    edges: list[dict] = []
    for source, file, calls in pending:
        for name in sorted(calls):
            candidates = by_name.get(name, [])
            local = [node for node in candidates if node["file"] == file]
            resolved = local if len(local) == 1 else candidates if len(candidates) == 1 else []
            if resolved and resolved[0]["id"] != source:
                edges.append({"from": source, "to": resolved[0]["id"], "basis": "static call"})
    return {
        "nodes": nodes[:300],
        "edges": edges[:500],
        "node_count": len(nodes),
        "edge_count": len(edges),
        "basis": "possible calls inferred from Python syntax",
    }


def neighbors(graph: dict, locations: list[dict]) -> list[dict]:
    targets = {f"{item['file']}::{item['symbol']}" for item in locations}
    edges = [edge for edge in graph["edges"] if edge["from"] in targets or edge["to"] in targets]
    return edges[:20]
