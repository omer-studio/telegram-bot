import json
import os
import threading
from datetime import datetime
from typing import Any, Dict
# save_gpt_call_log הועברה למערכת interactions_log החדשה


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
        """Save to SQL database instead of file (SHELL migration complete)."""
        # כל הנתונים נשמרים ל-SQL דרך log_gpt_call - לא צריך קובץ יותר
        pass

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
        רושם קריאה ל-SQL database בפורמט אחיד, ללא תלות ב-client.
        :param log_path: נתיב הקובץ (לא בשימוש ב-SQL)
        :param gpt_type: סוג ה־GPT (A/B/C/D/E)
        :param request: פרטי הבקשה (messages, model וכו')
        :param response: פרטי התשובה (כולל usage)
        :param cost_usd: עלות (אם ידועה)
        :param extra: שדות נוספים (chat_id, message_id, gpt_pure_latency וכו')
        """
        print(f"[DEBUG][log_gpt_call] called! gpt_type={gpt_type}")
        print(f"[DEBUG][log_gpt_call] request: {json.dumps(request, ensure_ascii=False)[:500]}")
        print(f"[DEBUG][log_gpt_call] response: {str(response)[:500]}")
        print(f"[DEBUG][log_gpt_call] cost_usd: {cost_usd} extra: {extra}")
        
        try:
            # חילוץ פרטים מהתגובה
            chat_id = extra.get("chat_id") if extra else None
            usage = response.get("usage", {})
            tokens_input = usage.get("prompt_tokens", 0)
            tokens_output = usage.get("completion_tokens", 0)
            
            # 🔥 תיקון: שמירת זמן עיבוד טהור מ-extra
            processing_time = 0
            if extra:
                processing_time = extra.get("gpt_pure_latency", 0)
                if processing_time == 0:
                    processing_time = extra.get("processing_time_seconds", 0)
                if processing_time == 0:
                    processing_time = extra.get("total_time", 0)
            
            # הדפסת המידע החשוב על זמן העיבוד
            if processing_time > 0:
                print(f"⏱️ [DEBUG][log_gpt_call] Processing time: {processing_time:.3f}s")
            
            # שמירה ל-SQL הועברה למערכת interactions_log החדשה
            print(f"[GPT_JSONL_LOGGER] {gpt_type} - {request.get('model', 'unknown')} - {tokens_input}/{tokens_output} tokens - ${cost_usd or 0:.4f} - {processing_time:.2f}s")
            
            print(f"[DEBUG][log_gpt_call] Successfully saved to SQL")
            
        except Exception as sql_exc:
            print(f"[LOGGING_ERROR] Failed to save to SQL: {sql_exc}")
            
        # 🚀 HTML מעודכן ברקע - לא מעכב את הבוט!
        # רק כל 10 קריאות כדי לא לעכב את המשתמש
        try:
            import threading
            import random
            
            # עדכון HTML רק מדי פעם כדי לא לעכב את המשתמש
            if random.randint(1, 10) == 1:  # 10% מהזמן
                def update_html_background():
                    try:
                        import sys
                        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                        
                        from scripts.build_gpt_log import build_html, upload_to_drive
                        
                        build_html()
                        upload_to_drive("data/gpt_log.html")
                        print(f"[DEBUG][log_gpt_call] HTML updated in background")
                        
                    except Exception as html_exc:
                        print(f"[LOGGING_ERROR] Background HTML update failed: {html_exc}")
                
                # הפעלה ברקע - לא חוסמת את הבוט
                threading.Thread(target=update_html_background, daemon=True).start()
                
        except Exception as thread_exc:
            print(f"[LOGGING_ERROR] Failed to start background HTML update: {thread_exc}")