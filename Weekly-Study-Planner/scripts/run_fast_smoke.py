from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
UI_ROOT = REPO_ROOT / "saathi-ui"


CHECKS = [
    {
        "name": "api_hardening",
        "cmd": ["venv_linux313/bin/python", "tests/test_api_hardening.py"],
        "cwd": REPO_ROOT,
    },
    {
        "name": "auth_identity",
        "cmd": ["venv_linux313/bin/python", "tests/test_auth_identity.py"],
        "cwd": REPO_ROOT,
    },
    {
        "name": "dashboard_adapters",
        "cmd": ["node", "saathi-ui/scripts/test-dashboard-adapters.mjs"],
        "cwd": REPO_ROOT,
    },
    {
        "name": "client_state",
        "cmd": ["node", "saathi-ui/scripts/test-client-state.mjs"],
        "cwd": REPO_ROOT,
    },
    {
        "name": "frontend_lint",
        "cmd": ["npm", "run", "lint"],
        "cwd": UI_ROOT,
    },
    {
        "name": "frontend_build",
        "cmd": ["npm", "run", "build"],
        "cwd": UI_ROOT,
    },
]


def run_check(name: str, cmd: list[str], cwd: Path) -> tuple[bool, float]:
    print(f"\n=== {name} ===")
    print(f"$ {' '.join(cmd)}")
    started = time.perf_counter()
    result = subprocess.run(cmd, cwd=cwd)
    duration = time.perf_counter() - started
    ok = result.returncode == 0
    print(f"--- {name}: {'PASS' if ok else 'FAIL'} ({duration:.2f}s)")
    return ok, duration


def main() -> int:
    print("Running SkedioAI fast smoke suite...")
    total_started = time.perf_counter()
    failures: list[str] = []
    durations: list[tuple[str, float]] = []

    for check in CHECKS:
        ok, duration = run_check(check["name"], check["cmd"], check["cwd"])
        durations.append((check["name"], duration))
        if not ok:
            failures.append(check["name"])

    total_duration = time.perf_counter() - total_started

    print("\n=== summary ===")
    for name, duration in durations:
        print(f"- {name}: {duration:.2f}s")
    print(f"- total: {total_duration:.2f}s")

    if failures:
        print(f"\nFAILURES: {', '.join(failures)}")
        return 1

    print("\nAll fast smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
