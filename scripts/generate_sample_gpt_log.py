#!/usr/bin/env python3
"""Generate mock GPT log entries for local testing.

Run:
    python3 scripts/generate_sample_gpt_log.py [--n 20]

Creates/extends data/openai_calls.jsonl with *n* synthetic records that
conform to the expected schema. Does **not** call the OpenAI API, so it
works offline and is safe for CI.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

LOG_PATH = os.path.join("data", "openai_calls.jsonl")
GPT_MODELS = ["gpt-4", "gpt-3.5-turbo", "gpt-4o-mini"]
GPT_TYPES = list("ABCD")


def random_messages() -> List[Dict[str, str]]:
    user_q = random.choice([
        "מה השעה?",
        "איך אומרים כלב בצרפתית?",
        "כתוב לי בדיחה על פינגווינים.",
        "תן לי מתכון לחומוס.",
    ])
    return [
        {"role": "user", "content": user_q},
        {"role": "assistant", "content": "תשובה אקראית"},
    ]


def synth_entry() -> Dict[str, Any]:
    prompt_t = random.randint(200, 800)
    completion_t = random.randint(50, 300)
    total_t = prompt_t + completion_t + random.randint(0, 120)  # cached?
    cost_usd = round(total_t * 1e-5, 4)

    return {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cost_usd": cost_usd,
        "request": {
            "model": random.choice(GPT_MODELS),
            "messages": random_messages(),
        },
        "response": {
            "id": f"chatcmpl-{uuid.uuid4().hex[:6]}",
            "choices": [{"message": {"content": "תשובה סינתטית"}}],
            "usage": {
                "prompt_tokens": prompt_t,
                "completion_tokens": completion_t,
                "total_tokens": total_t,
            },
        },
        "gpt_type": random.choice(GPT_TYPES),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate sample GPT log entries")
    parser.add_argument("--n", type=int, default=5, help="Number of records to append")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(LOG_PATH) or ".", exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        for _ in range(args.n):
            fh.write(json.dumps(synth_entry(), ensure_ascii=False) + "\n")

    print(f"✅ Added {args.n} fake entries to {LOG_PATH}")


if __name__ == "__main__":
    main()