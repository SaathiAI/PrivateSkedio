from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local dependency
    load_dotenv = None


def build_headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_json(url: str, headers: dict[str, str]) -> tuple[int, object]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        if not body:
            return response.status, None
        try:
            return response.status, json.loads(body)
        except json.JSONDecodeError:
            return response.status, body


def measure_once(url: str, headers: dict[str, str]) -> dict[str, object]:
    started = time.perf_counter()
    status, payload = fetch_json(url, headers)
    duration_ms = (time.perf_counter() - started) * 1000
    return {
        "url": url,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "payload": payload,
    }


def summarize(label: str, runs: list[float]) -> None:
    print(
        f"{label}: min={min(runs):.2f}ms avg={statistics.mean(runs):.2f}ms "
        f"max={max(runs):.2f}ms"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure SkedioAI app boot API latency.",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("SAATHI_API_URL", "http://127.0.0.1:8000"),
        help="Backend base URL.",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("SAATHI_BEARER_TOKEN"),
        help="Bearer token for authenticated endpoints.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="How many times to measure each path.",
    )
    args = parser.parse_args()

    if load_dotenv is not None:
        load_dotenv()

    base_url = args.base_url.rstrip("/")
    headers = build_headers(args.token)

    health_runs: list[float] = []
    old_parallel_runs: list[float] = []
    new_bootstrap_runs: list[float] = []

    print(f"base_url={base_url}")
    print(f"runs={args.runs}")
    print(f"has_token={bool(args.token)}")

    for run in range(1, args.runs + 1):
        print(f"\nrun={run}")

        health = measure_once(f"{base_url}/health", build_headers(None))
        health_runs.append(float(health["duration_ms"]))
        print(
            f"health status={health['status']} duration_ms={health['duration_ms']}"
        )

        if not args.token:
            continue

        old_urls = [
            f"{base_url}/v2/plan/active",
            f"{base_url}/plan/progress",
            f"{base_url}/stats/dashboard",
        ]

        old_started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=3) as executor:
            old_results = list(executor.map(lambda url: measure_once(url, headers), old_urls))
        old_wall_ms = (time.perf_counter() - old_started) * 1000
        old_parallel_runs.append(old_wall_ms)
        print(f"old_boot_parallel duration_ms={old_wall_ms:.2f}")
        for item in old_results:
            print(
                f"  endpoint={item['url'].split(base_url)[-1]} "
                f"status={item['status']} duration_ms={item['duration_ms']}"
            )

        new_bootstrap = measure_once(f"{base_url}/app/bootstrap", headers)
        new_bootstrap_runs.append(float(new_bootstrap["duration_ms"]))
        print(
            f"new_bootstrap status={new_bootstrap['status']} "
            f"duration_ms={new_bootstrap['duration_ms']}"
        )

    print("\nsummary")
    summarize("health", health_runs)

    if args.token and old_parallel_runs and new_bootstrap_runs:
        summarize("old_boot_parallel", old_parallel_runs)
        summarize("new_bootstrap", new_bootstrap_runs)
        print(
            "frontend_boot_estimate: roughly new_bootstrap + auth/session overhead "
            "(usually a few hundred ms locally when backend is already awake)"
        )
    elif not args.token:
        print("No bearer token provided, so only /health was measured.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.HTTPError as error:
        print(f"HTTPError status={error.code} url={error.url}")
        try:
            print(error.read().decode("utf-8"))
        except Exception:
            pass
        raise
