"""Export a full LangSmith trace tree to a local JSON file.

Usage:
    python scripts/export_langsmith_trace.py <trace-or-run-id-or-url>

The script accepts either:
- a root trace/run UUID
- a LangSmith run URL containing a UUID

It writes every run/span in that trace to logs/langsmith_trace_<trace_id>.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langsmith import Client


UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def extract_uuid(value: str) -> str:
    match = UUID_RE.search(value)
    if not match:
        raise SystemExit(
            "Could not find a UUID in the argument. Copy the root LangSmith ID or URL."
        )
    return match.group(0)


def jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False, default=str)
        return value
    except TypeError:
        return str(value)


def run_to_dict(run: Any) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "trace_id": str(run.trace_id) if run.trace_id else None,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "name": run.name,
        "run_type": run.run_type,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "dotted_order": getattr(run, "dotted_order", None),
        "inputs": jsonable(run.inputs),
        "outputs": jsonable(run.outputs),
        "error": run.error,
        "extra": jsonable(run.extra),
        "events": jsonable(run.events),
        "tags": list(run.tags or []),
        "metadata": jsonable(getattr(run, "metadata", None)),
        "total_tokens": getattr(run, "total_tokens", None),
        "prompt_tokens": getattr(run, "prompt_tokens", None),
        "completion_tokens": getattr(run, "completion_tokens", None),
        "latency_ms": (
            round((run.end_time - run.start_time).total_seconds() * 1000, 2)
            if run.start_time and run.end_time
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_or_run", help="LangSmith trace/run UUID or URL")
    parser.add_argument(
        "--project",
        default=os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT"),
        help="Optional LangSmith project name. Defaults to LANGCHAIN_PROJECT/LANGSMITH_PROJECT.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional output file path. Defaults to logs/langsmith_trace_<trace_id>.json.",
    )
    args = parser.parse_args()

    root_or_trace_id = extract_uuid(args.trace_or_run)

    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    client = Client()

    root_run = client.read_run(root_or_trace_id)
    trace_id = str(root_run.trace_id or root_run.id)

    runs = list(
        client.list_runs(
            project_name=args.project,
            trace_id=trace_id,
            limit=None,
        )
    )

    runs.sort(
        key=lambda run: (
            getattr(run, "dotted_order", "") or "",
            run.start_time.isoformat() if run.start_time else "",
            str(run.id),
        )
    )

    output = {
        "trace_id": trace_id,
        "root_run_id": str(root_run.id),
        "project": args.project,
        "run_count": len(runs),
        "runs": [run_to_dict(run) for run in runs],
    }

    out_path = (
        Path(args.out)
        if args.out
        else repo_root / "logs" / f"langsmith_trace_{trace_id}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"Exported {len(runs)} runs")
    print(f"Trace ID: {trace_id}")
    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
