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

    @staticmethod
    def log_gpt_call(
        log_path: str,
        gpt_type: str,
        request: dict,
        response: dict,
        cost_usd: float = None,
        extra: dict = None,
    ) -> None:
        """
        רושם קריאה ל־openai_calls.jsonl בפורמט אחיד, ללא תלות ב-client.
        :param log_path: נתיב הקובץ
        :param gpt_type: סוג ה־GPT (A/B/C/D/E)
        :param request: פרטי הבקשה (messages, model וכו')
        :param response: פרטי התשובה (כולל usage)
        :param cost_usd: עלות (אם ידועה)
        :param extra: שדות נוספים (chat_id, message_id וכו')
        """
        print(f"[DEBUG][log_gpt_call] called! log_path={log_path} gpt_type={gpt_type}")
        print(f"[DEBUG][log_gpt_call] request: {json.dumps(request, ensure_ascii=False)[:500]}")
        print(f"[DEBUG][log_gpt_call] response: {str(response)[:500]}")
        print(f"[DEBUG][log_gpt_call] cost_usd: {cost_usd} extra: {extra}")
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "gpt_type": gpt_type,
            "request": request,
            "response": response,
        }
        if cost_usd is not None:
            entry["cost_usd"] = cost_usd
        if extra:
            entry.update(extra)
        # יצירת התיקייה אם צריך
        try:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        except Exception as e:
            print(f"[LOGGING_ERROR] Failed to create log dir: {e}")
        # כתיבה לקובץ (thread-safe)
        lock = threading.Lock()
        try:
            with lock:
                with open(log_path, "a", encoding="utf-8") as file:
                    file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            print(f"[DEBUG][log_gpt_call] Successfully wrote to {log_path}")
        except Exception as write_exc:
            print(f"[LOGGING_ERROR] Failed to write log: {write_exc}")
        # הפעלת build_gpt_log.py --upload לעדכון ה-HTML בדרייב
        try:
            # במקום subprocess - הפעלה ישירה של הפונקציות
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            # ייבוא הפונקציות ישירות
            from scripts.build_gpt_log import build_html, upload_to_drive
            
            # בניית ה-HTML
            build_html()
            print(f"[DEBUG][log_gpt_call] Successfully built HTML")
            
            # העלאה לדרייב
            upload_to_drive("data/gpt_log.html")
            print(f"[DEBUG][log_gpt_call] Successfully uploaded to Drive")
            
        except Exception as html_exc:
            print(f"[LOGGING_ERROR] Failed to update HTML log: {html_exc}")
            print(f"[LOGGING_ERROR] Full error: {str(html_exc)}")