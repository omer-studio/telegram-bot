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
    def chat_completion(
        self,
        client: Any,
        /,
        *,
        cost_usd: float | None = None,
        **payload: Any,
    ):
        """Provider-agnostic chat completion with automatic JSONL logging.

        Supported clients (first positional arg):
        • **OpenAI SDK** – pass an `openai.OpenAI()` instance (has `chat.completions.create`).
        • **LiteLLM** – pass the imported `litellm` module itself (has `completion`).

        The function detects the proper call, executes it, then logs:
        request, response, and ‑ אם קיים ‑ עלות (`cost_usd`) שחושבה ע"י `litellm.completion_cost`.
        """

        # Snapshot the original request for the log (avoid mutation by SDKs)
        request_copy: Dict[str, Any] = json.loads(json.dumps(payload, default=str))

        # ------------------------------------------------------------------
        # Execute the completion call depending on the client type
        # ------------------------------------------------------------------
        if hasattr(client, "chat") and hasattr(client.chat, "completions"):
            # OpenAI-style SDK ≥1.0
            response = client.chat.completions.create(**payload)
            endpoint_name = "chat/completions"
        elif hasattr(client, "completion"):
            # LiteLLM shim (supports OpenAI, Gemini, Anthropic…)
            response = client.completion(**payload)  # type: ignore[attr-defined]
            endpoint_name = "litellm/completion"
        else:
            raise ValueError(
                "Unsupported client passed to GPTJSONLLogger. "
                "Pass an OpenAI client or the litellm module."
            )

        # ------------------------------------------------------------------
        # Serialise the response object to JSON-safe primitives
        # ------------------------------------------------------------------
        response_dict: Any
        try:
            response_dict = response.model_dump()  # type: ignore[attr-defined]
        except AttributeError:
            try:
                response_dict = response.to_dict_recursive()  # type: ignore[attr-defined]
            except AttributeError:
                response_dict = json.loads(json.dumps(response, default=str))

        # Append to log
        self._append_log(request_copy, response_dict, endpoint_name, cost_usd)
        return response

    # ------------------------------------------------------------------
    # Internal utils
    # ------------------------------------------------------------------
    def _append_log(
        self,
        request_body: Dict[str, Any],
        response_body: Any,
        endpoint_name: str,
        cost_usd: Any = None,
    ) -> None:
        """Append a single JSONL line atomically (thread-safe)."""
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "endpoint": endpoint_name,
            "request": request_body,
            "response": response_body,
        }
        if cost_usd is not None:
            entry["cost_usd"] = cost_usd

        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with open(self.log_path, "a", encoding="utf-8") as file:
                file.write(line + "\n")