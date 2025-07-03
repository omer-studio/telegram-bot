import os

# The OpenAI SDK must be installed; otherwise this script will not run.
# We import inside a try/except so static linters in environments without the
# package do not complain.
try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover – runtime only
    OpenAI = None  # type: ignore

# >>> Replace with your real key or rely on env var OPENAI_API_KEY
# os.environ["OPENAI_API_KEY"] = "sk-..."

from gpt_jsonl_logger import GPTJSONLLogger


def main():
    # Ensure the SDK is available before instantiating
    if OpenAI is None:  # type: ignore
        raise ImportError("The 'openai' package is required. Run: pip install openai>=1.0")

    # Initialise the OpenAI client (from openai>=1.0)
    client = OpenAI()

    # You can place the log file wherever you want. Here we keep it under data/
    logger = GPTJSONLLogger("data/openai_calls.jsonl")

    # Standard chat payload – nothing special
    response = logger.chat_completion(
        client,
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a funny haiku about coffee."},
        ],
        temperature=0.5,
    )

    # If you already calculated cost elsewhere, pass it in:
    # logger.chat_completion(client, cost_usd=0.0021, **same_payload)

    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()