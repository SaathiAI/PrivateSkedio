#!/usr/bin/env python3
"""
LangSmith Trace Viewer
======================
Fetches a trace from LangSmith and prints a tree visualization.
Saves output to a log file for analysis.

Usage:
    python scripts/trace_viewer.py <run_id>
    python scripts/trace_viewer.py 2f0b6e40-7d90-4a6e-a74e-f96c27b0114c
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

from langsmith import Client


def get_duration_ms(run):
    """Calculate duration in milliseconds from run timestamps."""
    if run.end_time and run.start_time:
        return (run.end_time - run.start_time).total_seconds() * 1000
    return None


def format_duration(ms):
    """Format duration for display."""
    if ms is None:
        return ""
    if ms < 1000:
        return f"{ms:.0f}ms"
    return f"{ms/1000:.2f}s"


def build_tree(client, run_id, depth=0, max_depth=10):
    """Recursively build a trace tree from LangSmith runs."""
    if depth > max_depth:
        return []
    
    runs = list(client.list_runs(parent_run_id=run_id))
    tree = []
    
    for run in runs:
        duration = get_duration_ms(run)
        node = {
            "id": str(run.id),
            "name": run.name,
            "run_type": run.run_type,
            "duration_ms": duration,
            "duration_str": format_duration(duration),
            "children": build_tree(client, run.id, depth + 1, max_depth),
        }
        tree.append(node)
    
    return tree


def print_tree(nodes, indent=0, is_last=True, prefix="", file=None):
    """Print the tree with nice formatting."""
    for i, node in enumerate(nodes):
        is_last_node = i == len(nodes) - 1
        
        if indent == 0:
            connector = ""
            child_prefix = ""
        else:
            connector = "└── " if is_last_node else "├── "
            child_prefix = "    " if is_last_node else "│   "
        
        duration_str = f" {node['duration_str']}" if node['duration_str'] else ""
        run_type = f" [{node['run_type']}]" if node['run_type'] != 'chain' else ""
        
        line = f"{prefix}{connector}{node['name']}{duration_str}{run_type}"
        print(line, file=file)
        
        if node['children']:
            print_tree(
                node['children'],
                indent + 1,
                is_last_node,
                prefix + child_prefix,
                file=file
            )


def print_waterfall(nodes, start_time=None, indent=0, prefix="", file=None):
    """Print a waterfall view showing timing bars."""
    for i, node in enumerate(nodes):
        is_last_node = i == len(nodes) - 1
        
        if indent == 0:
            connector = ""
            child_prefix = ""
        else:
            connector = "└── " if is_last_node else "├── "
            child_prefix = "    " if is_last_node else "│   "
        
        duration = node['duration_ms']
        if duration:
            bar_len = min(int(duration / 500), 30)  # 500ms = 1 char, max 30
            bar = "█" * bar_len
            duration_str = f" {format_duration(duration)}"
        else:
            bar = ""
            duration_str = ""
        
        line = f"{prefix}{connector}{node['name']}{duration_str}"
        if bar:
            line += f"  {bar}"
        
        print(line, file=file)
        
        if node['children']:
            print_waterfall(
                node['children'],
                start_time,
                indent + 1,
                prefix + child_prefix,
                file=file
            )


def calculate_stats(nodes, stats=None):
    """Calculate aggregate statistics from the tree."""
    if stats is None:
        stats = {
            "total_runs": 0,
            "llm_calls": 0,
            "tool_calls": 0,
            "total_duration_ms": 0,
            "max_depth": 0,
            "by_type": {},
            "by_name": {},
        }
    
    for node in nodes:
        stats["total_runs"] += 1
        
        run_type = node["run_type"]
        stats["by_type"][run_type] = stats["by_type"].get(run_type, 0) + 1
        
        name = node["name"]
        stats["by_name"][name] = stats["by_name"].get(name, 0) + 1
        
        if run_type == "llm":
            stats["llm_calls"] += 1
        elif run_type == "tool":
            stats["tool_calls"] += 1
        
        if node["duration_ms"]:
            stats["total_duration_ms"] += node["duration_ms"]
        
        if node["children"]:
            calculate_stats(node["children"], stats)
    
    return stats


def main():
    if len(sys.argv) < 2:
        print("Usage: python trace_viewer.py <run_id>")
        print("Example: python trace_viewer.py 2f0b6e40-7d90-4a6e-a74e-f96c27b0114c")
        sys.exit(1)
    
    run_id = sys.argv[1]
    
    # Create logs directory
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Create log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"trace_{run_id[:8]}_{timestamp}.log"
    
    print(f"Fetching trace: {run_id}")
    print(f"Log file: {log_file}")
    print()
    
    client = Client()
    
    # Read the root run
    try:
        root_run = client.read_run(run_id)
    except Exception as e:
        print(f"Error fetching run: {e}")
        sys.exit(1)
    
    # Build the tree
    tree = [{
        "id": str(root_run.id),
        "name": root_run.name,
        "run_type": root_run.run_type,
        "duration_ms": get_duration_ms(root_run),
        "duration_str": format_duration(get_duration_ms(root_run)),
        "children": build_tree(client, run_id),
    }]
    
    # Write to log file
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write(f"LangSmith Trace: {run_id}\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 80 + "\n\n")
        
        f.write("TREE VIEW\n")
        f.write("-" * 40 + "\n")
        print_tree(tree, file=f)
        
        f.write("\n\nWATERFALL VIEW\n")
        f.write("-" * 40 + "\n")
        print_waterfall(tree, file=f)
        
        # Stats
        stats = calculate_stats(tree)
        f.write("\n\nSTATISTICS\n")
        f.write("-" * 40 + "\n")
        f.write(f"Total runs: {stats['total_runs']}\n")
        f.write(f"LLM calls: {stats['llm_calls']}\n")
        f.write(f"Tool calls: {stats['tool_calls']}\n")
        f.write(f"Total duration: {format_duration(stats['total_duration_ms'])}\n")
        f.write(f"\nBy type:\n")
        for t, count in sorted(stats['by_type'].items()):
            f.write(f"  {t}: {count}\n")
        f.write(f"\nBy name:\n")
        for name, count in sorted(stats['by_name'].items(), key=lambda x: -x[1]):
            f.write(f"  {name}: {count}\n")
    
    # Also print to console
    print("TREE VIEW")
    print("-" * 40)
    print_tree(tree)
    
    print("\n\nWATERFALL VIEW")
    print("-" * 40)
    print_waterfall(tree)
    
    stats = calculate_stats(tree)
    print("\n\nSTATISTICS")
    print("-" * 40)
    print(f"Total runs: {stats['total_runs']}")
    print(f"LLM calls: {stats['llm_calls']}")
    print(f"Tool calls: {stats['tool_calls']}")
    print(f"Total duration: {format_duration(stats['total_duration_ms'])}")
    
    print(f"\nLog saved to: {log_file}")


if __name__ == "__main__":
    main()
