import argparse
import os
import statistics
import time

from openai import OpenAI

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local dependency
    load_dotenv = None


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure raw OpenAI model latency.")
    parser.add_argument("--model", default="gpt-5-mini", help="Model name to test.")
    parser.add_argument(
        "--input",
        default="Say hello",
        help="Prompt/input text to send to the model.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="How many times to call the model.",
    )
    args = parser.parse_args()

    if load_dotenv is not None:
        load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    client = OpenAI(api_key=api_key)
    latencies_ms = []

    print(f"model={args.model}")
    print(f"runs={args.runs}")
    print(f"input={args.input!r}")

    for run_number in range(1, args.runs + 1):
        t0 = time.perf_counter()
        response = client.responses.create(
            model=args.model,
            input=args.input,
        )
        t1 = time.perf_counter()

        latency_ms = (t1 - t0) * 1000
        latencies_ms.append(latency_ms)

        output_text = getattr(response, "output_text", "") or ""
        print(
            f"run={run_number} latency_ms={latency_ms:.2f} "
            f"output={output_text[:120]!r}"
        )

    print(f"min_ms={min(latencies_ms):.2f}")
    print(f"max_ms={max(latencies_ms):.2f}")
    print(f"avg_ms={statistics.mean(latencies_ms):.2f}")


if __name__ == "__main__":
    main()
