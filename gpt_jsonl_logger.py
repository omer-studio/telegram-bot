import json
import os
import threading
from datetime import datetime
from typing import Any, Dict


class GPTJSONLLogger:
    """A tiny helper that logs every call *and* response to OpenAI Chat API.

    • Each log line is a single JSON object → perfect for `jq`, BigQuery, Athena, etc.
    • Thread-safe append so you can share one logger instance across your whole app.
    • Fully self-contained: no external deps besides the `openai` client you already use.

    Usage (Python ≥3.8):
    -----------------------------------------------------------------------
    from openai import OpenAI
    from gpt_jsonl_logger import GPTJSONLLogger

    client = OpenAI()  # relies on env var OPENAI_API_KEY
    logger = GPTJSONLLogger("data/openai_calls.jsonl")

    response = logger.chat_completion(
        client,
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ],
        temperature=0.7,
    )

    print(response.choices[0].message.content)
    -----------------------------------------------------------------------
    """

    def __init__(self, log_path: str = "openai_calls.jsonl") -> None:
        self.log_path = log_path
        # Make sure parent directory exists (but ignore if log_path has no dir part)
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def chat_completion(self, client: Any, /, **payload: Any):
        """Thin wrapper around ``client.chat.completions.create`` *with logging*.

        The original response object is returned unchanged so your existing code
        keeps working. The request payload **and** serialised response are
        appended to ``self.log_path`` as a single JSON object.
        """
        # Keep a deep-ish copy of what the caller sent (it may be mutated by SDK)
        request_copy: Dict[str, Any] = json.loads(json.dumps(payload, default=str))

        response = client.chat.completions.create(**payload)

        # Convert response object to plain Python primitives so it's JSON-friendly
        response_dict: Any
        try:
            # openai>=1.0 uses Pydantic -> model_dump()
            response_dict = response.model_dump()
        except AttributeError:
            try:
                # openai<1.0 legacy helper
                response_dict = response.to_dict_recursive()
            except AttributeError:
                # Fallback – best-effort string representation
                response_dict = str(response)

        self._append_log(request_copy, response_dict)
        return response

    # ------------------------------------------------------------------
    # Internal utils
    # ------------------------------------------------------------------
    def _append_log(self, request_body: Dict[str, Any], response_body: Any) -> None:
        """Append a single JSONL line atomically (thread-safe)."""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "endpoint": "chat/completions",
            "request": request_body,
            "response": response_body,
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as file:
                file.write(line + "\n")