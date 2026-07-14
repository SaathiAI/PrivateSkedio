"""Simple GPT-5-mini conversation loop with timestamps + GPT-5 config."""

import os
import time
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    raise SystemExit("Install openai: pip install openai")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("OPENAI_API_KEY not set in env or .env file")

client = OpenAI(api_key=api_key)

SYSTEM_PROMPT = "You are a helpful assistant. Keep replies short."

history = []

print("=== GPT-5-mini Responses API Chat Test ===")
print("Type 'quit' to exit, 'clear' to reset history\n")

turn = 0

while True:
    user_input = input("You: ").strip()

    if user_input.lower() == "quit":
        break

    if user_input.lower() == "clear":
        history = []
        turn = 0
        print("[history cleared]\n")
        continue

    if not user_input:
        continue

    turn += 1
    history.append({"role": "user", "content": user_input})

    start = time.perf_counter()

    response = client.responses.create(
        model="gpt-4.1-mini",
        instructions=SYSTEM_PROMPT,
        input=history,
    )

    end = time.perf_counter()

    reply = response.output_text or ""

    latency_ms = (end - start) * 1000
    timestamp = datetime.now().strftime("%H:%M:%S")

    usage = response.usage
    tokens_in = usage.input_tokens if usage else 0
    tokens_out = usage.output_tokens if usage else 0
    reasoning_tokens = (
        usage.output_tokens_details.reasoning_tokens
        if usage and usage.output_tokens_details
        else 0
    )

    history.append({"role": "assistant", "content": reply})

    print(
        f"[{timestamp}] "
        f"({latency_ms:.0f}ms | in:{tokens_in} out:{tokens_out} "
        f"reasoning:{reasoning_tokens} tokens)"
    )
    print(f"Assistant: {reply}\n")