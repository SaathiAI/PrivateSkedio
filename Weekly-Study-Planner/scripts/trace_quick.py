#!/usr/bin/env python3
"""
LangSmith Trace Viewer - Quick
===============================
Fetches recent traces from your project and displays them.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Load .env manually
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from langsmith import Client


def get_duration_ms(run):
    if run.end_time and run.start_time:
        return (run.end_time - run.start_time).total_seconds() * 1000
    return None


def fmt(ms):
    if ms is None:
        return ""
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms/1000:.2f}s"


def build_children(client, parent_id, depth=0):
    if depth > 15:
        return []
    children = []
    for run in client.list_runs(parent_run_id=parent_id):
        children.append({
            "name": run.name,
            "type": run.run_type,
            "ms": get_duration_ms(run),
            "children": build_children(client, run.id, depth + 1),
        })
    return children


def print_tree(nodes, prefix="", file=None):
    for i, n in enumerate(nodes):
        last = i == len(nodes) - 1
        conn = "└── " if last else "├── "
        child_p = prefix + ("    " if last else "│   ")
        
        dur = f" {fmt(n['ms'])}" if n['ms'] else ""
        bar = ""
        if n['ms']:
            bar_len = min(int(n['ms'] / 500), 40)
            bar = " " + "█" * bar_len
        
        print(f"{prefix}{conn}{n['name']}{dur}{bar}", file=file)
        
        if n['children']:
            print_tree(n['children'], child_p, file=file)


def main():
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    client = Client()
    project = os.environ.get("LANGSMITH_PROJECT", "saathi-final-eval-v1")
    
    print(f"Fetching recent traces from: {project}\n")
    
    # Get root runs (top-level traces)
    roots = list(client.list_runs(
        project_name=project,
        is_root=True,
        limit=10,
    ))
    
    if not roots:
        print("No traces found.")
        return
    
    # Show list
    print("Recent traces:")
    print("-" * 60)
    for i, r in enumerate(roots):
        dur = fmt(get_duration_ms(r))
        ts = r.start_time.strftime("%Y-%m-%d %H:%M") if r.start_time else "?"
        print(f"  [{i}] {r.name} | {dur} | {ts}")
    print()
    
    # Pick first one (or let user choose)
    if len(sys.argv) > 1:
        idx = int(sys.argv[1])
    else:
        idx = 0
    
    chosen = roots[idx]
    print(f"Loading trace: {chosen.name} ({chosen.id})\n")
    
    # Build tree
    tree = [{
        "name": chosen.name,
        "type": chosen.run_type,
        "ms": get_duration_ms(chosen),
        "children": build_children(client, chosen.id),
    }]
    
    # Print
    print("=" * 60)
    print_tree(tree)
    print("=" * 60)
    
    # Save to log
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"trace_{ts}.log"
    with open(log_file, "w") as f:
        f.write(f"Trace: {chosen.id}\n")
        f.write(f"Name: {chosen.name}\n")
        f.write(f"Time: {chosen.start_time}\n\n")
        print_tree(tree, file=f)
    
    print(f"\nSaved to: {log_file}")


if __name__ == "__main__":
    main()
