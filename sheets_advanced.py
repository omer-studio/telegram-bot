"""
sheets_advanced.py - Queue, לוגים מתקדמים וחישובי עלויות
"""

import asyncio
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from config import (
    setup_google_sheets,
    MAX_SHEETS_OPERATIONS_PER_MINUTE,
    SHEETS_QUEUE_SIZE,
    SHEETS_BATCH_SIZE,
    UPDATE_PRIORITY,
    gpt_log_path
)
from gpt_utils import calculate_gpt_cost, USD_TO_ILS
from sheets_core import debug_log, safe_int, safe_float
from notifications import send_error_notification

# ================================
# 🚀 מערכת Queue מתקדמת
# ================================

class SheetsOperation:
    def __init__(self, operation_type: str, priority: int, data: dict, retry_count: int = 0):
        self.operation_type = operation_type
        self.priority = priority
        self.data = data
        self.retry_count = retry_count
        self.created_at = time.time()
    
    def __lt__(self, other):
        return self.priority < other.priority

class SheetsQueueManager:
    def __init__(self):
        self.queue = asyncio.PriorityQueue(maxsize=SHEETS_QUEUE_SIZE)
        self.rate_limiter = []
        self.processing = False
    
    async def add_operation(self, operation_type: str, priority_name: str, data: dict):
        priority = UPDATE_PRIORITY.get(priority_name, 2)
        operation = SheetsOperation(operation_type, priority, data)
        
        try:
            await self.queue.put(operation)
            debug_log(f"Added {operation_type} operation with priority {priority_name}", "SheetsQueue")
            
            if not self.processing:
                asyncio.create_task(self._process_queue())
        except asyncio.QueueFull:
            debug_log(f"Queue full! Dropping {operation_type} operation", "SheetsQueue")
    
    async def _process_queue(self):
        if self.processing:
            return
        
        self.processing = True
        debug_log("Started processing Sheets queue", "SheetsQueue")
        
        try:
            while not self.queue.empty():
                if not self._can_execute():
                    await asyncio.sleep(1)
                    continue
                
                batch = []
                for _ in range(min(SHEETS_BATCH_SIZE, self.queue.qsize())):
                    try:
                        operation = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                        batch.append(operation)
                    except asyncio.TimeoutError:
                        break
                
                if batch:
                    await self._execute_batch(batch)
        finally:
            self.processing = False
            debug_log("Finished processing Sheets queue", "SheetsQueue")
    
    def _can_execute(self) -> bool:
        now = time.time()
        self.rate_limiter = [ts for ts in self.rate_limiter if now - ts < 60]
        return len(self.rate_limiter) < MAX_SHEETS_OPERATIONS_PER_MINUTE
    
    async def _execute_batch(self, batch: List[SheetsOperation]):
        for operation in batch:
            try:
                await self._execute_operation(operation)
                self.rate_limiter.append(time.time())
            except Exception as e:
                debug_log(f"Failed to execute {operation.operation_type}: {e}", "SheetsQueue")
                if operation.priority == 1 and operation.retry_count < 3:
                    operation.retry_count += 1
                    await self.queue.put(operation)
    
    async def _execute_operation(self, operation: SheetsOperation):
        await asyncio.to_thread(execute_sheets_operation_sync, operation.operation_type, operation.data)

sheets_queue_manager = SheetsQueueManager()

def execute_sheets_operation_sync(operation_type: str, data: dict):
    if operation_type == "log_to_sheets":
        return log_to_sheets_sync(**data)
    elif operation_type == "update_profile":
        return update_user_profile_sync(data["chat_id"], data["field_values"])
    elif operation_type == "increment_code_try":
        from sheets_core import increment_code_try_sync
        return increment_code_try_sync(data["sheet_states"], data["chat_id"])
    else:
        debug_log(f"Unknown operation type: {operation_type}", "SheetsQueue")
        return False

# ================================
# 💰 חישובי עלויות מתקדמים
# ================================

def clean_cost_value(cost_val) -> float:
    if cost_val is None or cost_val == "" or cost_val == "N/A":
        return 0.0
    
    try:
        if isinstance(cost_val, str):
            cleaned = cost_val.replace("$", "").replace("₪", "").replace(",", "").strip()
            return float(cleaned) if cleaned else 0.0
        return float(cost_val)
    except (ValueError, TypeError) as e:
        debug_log(f"Invalid cost value: {cost_val}, error: {e}", "CostCalc")
        return 0.0

def format_money(value) -> str:
    try:
        num_value = clean_cost_value(value)
        return f"{num_value:.3f}" if num_value != 0 else "0.00"
    except Exception as e:
        debug_log(f"Error formatting money value {value}: {e}", "CostCalc")
        return "0.00"

def agorot_from_usd(cost_usd: float) -> int:
    try:
        cost_ils = cost_usd * USD_TO_ILS
        return int(cost_ils * 100)
    except (ValueError, TypeError) as e:
        debug_log(f"Error converting USD to agorot {cost_usd}: {e}", "CostCalc")
        return 0

def calculate_costs_unified(usage_dict: Dict) -> Dict[str, float]:
    try:
        if not usage_dict or not isinstance(usage_dict, dict):
            return {"cost_usd": 0, "cost_ils": 0, "cost_agorot": 0}
        
        model = usage_dict.get("model", "gpt-4")
        prompt_tokens = safe_int(usage_dict.get("prompt_tokens", 0))
        completion_tokens = safe_int(usage_dict.get("completion_tokens", 0))
        cached_tokens = safe_int(usage_dict.get("cached_tokens", 0))
        
        existing_cost_usd = safe_float(usage_dict.get("cost_total", 0))
        if existing_cost_usd > 0:
            cost_usd = existing_cost_usd
        else:
            cost_info = calculate_gpt_cost(
                model_name=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_tokens=cached_tokens
            )
            # calculate_gpt_cost מחזיר dict – נשלוף רק cost_total (יהיה 0 אם אין completion_response)
            cost_usd = safe_float(cost_info.get("cost_total", 0))
        cost_ils = cost_usd * USD_TO_ILS
        cost_agorot = cost_ils * 100
        
        return {
            "cost_usd": cost_usd,
            "cost_ils": cost_ils,
            "cost_agorot": cost_agorot
        }
    except Exception as e:
        debug_log(f"Error calculating costs: {e}", "CostCalc")
        return {"cost_usd": 0, "cost_ils": 0, "cost_agorot": 0}

def debug_usage_dict(name: str, usage: Optional[Dict]) -> None:
    if not usage:
        debug_log(f"{name}: None", "CostCalc")
        return
    
    model = usage.get("model", "unknown")
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    cached_tokens = usage.get("cached_tokens", 0)
    
    debug_log(f"{name}: {model} | prompt:{prompt_tokens} completion:{completion_tokens} cached:{cached_tokens}", "CostCalc")

def validate_cost_data(cost_data: Dict) -> Dict:
    validated = {}
    
    numeric_fields = [
        "total_cost_usd", "total_cost_ils", "total_tokens",
        "prompt_tokens_total", "completion_tokens_total", "cached_tokens_total"
    ]
    
    for field in numeric_fields:
        value = cost_data.get(field, 0)
        validated[field] = max(0, clean_cost_value(value))
    
    validated["cost_breakdown"] = cost_data.get("cost_breakdown", {})
    return validated

def calculate_cost_per_message(total_cost_usd: float, message_count: int) -> float:
    try:
        return total_cost_usd / message_count if message_count > 0 else 0.0
    except (ValueError, TypeError, ZeroDivisionError) as e:
        debug_log(f"Error calculating cost per message {total_cost_usd}/{message_count}: {e}", "CostCalc")
        return 0.0

def get_cost_tier(cost_usd: float) -> str:
    if cost_usd < 0.01:
        return "זול"
    elif cost_usd < 0.05:
        return "בינוני"
    elif cost_usd < 0.1:
        return "יקר"
    else:
        return "יקר מאוד"

# ================================
# 📊 לוגים מתקדמים ל-Google Sheets
# ================================

@dataclass
class LogRow:
    message_id: str
    chat_id: str
    user_msg: str
    user_summary: str
    bot_reply: str
    bot_summary: str
    total_tokens: int
    prompt_tokens_total: int
    completion_tokens_total: int
    cached_tokens: int
    total_cost_usd: float
    total_cost_ils: float

def log_to_sheets_sync(
    message_id, chat_id, user_msg, reply_text, reply_summary,
    main_usage, summary_usage, extract_usage, total_tokens,
    cost_usd, cost_ils,
    prompt_tokens_total=None, completion_tokens_total=None, cached_tokens=None,
    cached_tokens_gpt_a=None, cost_gpt_a=None,
    cached_tokens_gpt_b=None, cost_gpt_b=None,
    cached_tokens_gpt_c=None, cost_gpt_c=None,
    merge_usage=None, fields_updated_by_gpt_c=None,
    gpt_d_usage=None, gpt_e_usage=None
):
    try:
        gc, sheet_users, sheet_log, sheet_states = setup_google_sheets()
        
        
        from utils import get_israel_time
        now = get_israel_time()  # משתמש באזור זמן ישראל במקום timezone לוקלי
        timestamp_full = now.strftime("%Y-%m-%d %H:%M:%S")
        date_only = now.strftime("%d/%m/%Y")
        time_only = now.strftime("%H:%M")

        if not message_id:
            message_id = f"msg_{now.strftime('%Y%m%d_%H%M%S')}"
            debug_log(f"יצירת message_id זמני: {message_id}", "SheetsLogger")
            
        if not chat_id:
            debug_log("שגיאה קריטית: chat_id ריק!", "SheetsLogger")
            return False

        debug_log(f"שמירת לוג: message_id={message_id}, chat_id={chat_id}", "SheetsLogger")

        # חישוב עלויות
        main_costs = calculate_costs_unified(main_usage)
        summary_costs = calculate_costs_unified(summary_usage)
        extract_costs = calculate_costs_unified(extract_usage)
        gpt_d_costs = calculate_costs_unified(gpt_d_usage) if gpt_d_usage else {"cost_usd": 0, "cost_ils": 0, "cost_agorot": 0}
        gpt_e_costs = calculate_costs_unified(gpt_e_usage) if gpt_e_usage else {"cost_usd": 0, "cost_ils": 0, "cost_agorot": 0}

        # חישוב סכומים כוללים
        total_cost_usd = (
            main_costs["cost_usd"] + 
            summary_costs["cost_usd"] + 
            extract_costs["cost_usd"] +
            gpt_d_costs["cost_usd"] +
            gpt_e_costs["cost_usd"]
        )
        total_cost_ils = total_cost_usd * USD_TO_ILS
        total_cost_agorot = total_cost_ils * 100

        # חישוב טוקנים
        main_prompt_clean = safe_int(main_usage.get("prompt_tokens", 0)) - safe_int(main_usage.get("cached_tokens", 0))
        summary_prompt_clean = safe_int(summary_usage.get("prompt_tokens", 0)) - safe_int(summary_usage.get("cached_tokens", 0))
        extract_prompt_clean = safe_int(extract_usage.get("prompt_tokens", 0)) - safe_int(extract_usage.get("cached_tokens", 0))

        prompt_tokens_total = (
            main_prompt_clean +
            summary_prompt_clean +
            extract_prompt_clean +
            (safe_int(merge_usage.get("prompt_tokens", 0)) - safe_int(merge_usage.get("cached_tokens", 0)) if merge_usage else 0)
        )

        completion_tokens_total = (
            safe_int(main_usage.get("completion_tokens", 0)) +
            safe_int(summary_usage.get("completion_tokens", 0)) +
            safe_int(extract_usage.get("completion_tokens", 0)) +
            (safe_int(merge_usage.get("completion_tokens", 0)) if merge_usage else 0)
        )

        cached_tokens = (
            safe_int(main_usage.get("cached_tokens", 0)) +
            safe_int(summary_usage.get("cached_tokens", 0)) +
            safe_int(extract_usage.get("cached_tokens", 0)) +
            (safe_int(merge_usage.get("cached_tokens", 0)) if merge_usage else 0)
        )

        total_tokens = prompt_tokens_total + completion_tokens_total + cached_tokens

        # בניית נתוני הלוג
        log_data = {
            "message_id": str(message_id),
            "chat_id": str(chat_id),
            "user_msg": user_msg if user_msg else "",
            "user_summary": "",
            "bot_reply": reply_text if reply_text else "",
            "bot_summary": reply_summary if reply_summary else "",
            "total_tokens": total_tokens,
            "prompt_tokens_total": prompt_tokens_total,
            "completion_tokens_total": completion_tokens_total,
            "cached_tokens": cached_tokens,
            "total_cost_usd": round(total_cost_usd, 6),
            "total_cost_ils": round(total_cost_agorot, 2),
            "timestamp": timestamp_full,
            "date_only": date_only,
            "time_only": time_only,
        }

        # הוספת נתוני GPT-A
        log_data.update({
            "usage_prompt_tokens_gpt_a": safe_int(main_usage.get("prompt_tokens", 0)) - safe_int(main_usage.get("cached_tokens", 0)),
            "usage_completion_tokens_gpt_a": safe_int(main_usage.get("completion_tokens", 0)),
            "usage_total_tokens_gpt_a": safe_int(main_usage.get("total_tokens", 0)),
            "cached_tokens_gpt_a": safe_int(main_usage.get("cached_tokens", 0)),
            "cost_gpt_a": main_costs["cost_agorot"],
            "model_gpt_a": str(main_usage.get("model", "")),
        })

        # הוספת נתוני GPT-B אם יש סיכום
        has_summary = summary_usage and len(summary_usage) > 0 and safe_float(summary_usage.get("completion_tokens", 0)) > 0
        if has_summary:
            log_data.update({
                "usage_prompt_tokens_gpt_b": safe_int(summary_usage.get("prompt_tokens", 0)) - safe_int(summary_usage.get("cached_tokens", 0)),
                "usage_completion_tokens_gpt_b": safe_int(summary_usage.get("completion_tokens", 0)),
                "usage_total_tokens_gpt_b": safe_int(summary_usage.get("total_tokens", 0)),
                "cached_tokens_gpt_b": safe_int(summary_usage.get("cached_tokens", 0)),
                "cost_gpt_b": summary_costs["cost_agorot"],
                "model_gpt_b": str(summary_usage.get("model", "")),
            })

        # הוספת נתוני GPT-C
        if isinstance(extract_usage, dict):
            log_data.update({
                "usage_prompt_tokens_gpt_c": safe_int(extract_usage.get("prompt_tokens", 0)) - safe_int(extract_usage.get("cached_tokens", 0)),
                "usage_completion_tokens_gpt_c": safe_int(extract_usage.get("completion_tokens", 0)),
                "usage_total_tokens_gpt_c": safe_int(extract_usage.get("total_tokens", 0)),
                "cached_tokens_gpt_c": safe_int(extract_usage.get("cached_tokens", 0)),
                "cost_gpt_c": extract_costs["cost_agorot"],
                "model_gpt_c": str(extract_usage.get("model", "")),
            })

        # הוספת שדות GPT-D ו-GPT-E אם קיימים
        if gpt_d_usage:
            log_data.update({
                "usage_tokens_gpt_d": safe_int(gpt_d_usage.get("total_tokens", 0)),
                "cost_gpt_d": gpt_d_costs["cost_agorot"],
                "model_gpt_d": str(gpt_d_usage.get("model", "")),
            })

        if gpt_e_usage:
            log_data.update({
                "usage_tokens_gpt_e": safe_int(gpt_e_usage.get("total_tokens", 0)),
                "cost_gpt_e": gpt_e_costs["cost_agorot"],
                "model_gpt_e": str(gpt_e_usage.get("model", "")),
            })

        # כתיבה לגיליון
        try:
            header = sheet_log.row_values(1)
            row_data = [""] * len(header)
            
            for i, col_name in enumerate(header):
                if col_name in log_data:
                    row_data[i] = str(log_data[col_name])

            # הכנסת שורה חדשה בשורה 3 (אחרי הכותרות) במקום הוספה בסוף
            sheet_log.insert_row(row_data, 3)
            debug_log(f"Successfully logged to sheets for message {message_id}", "SheetsLogger")
            return True
        except Exception as e:
            debug_log(f"Error writing to sheet: {e}", "SheetsLogger")
            return False

    except Exception as e:
        debug_log(f"Error in log_to_sheets_sync: {e}", "SheetsLogger")
        send_error_notification(f"Error in log_to_sheets_sync: {e}")
        return False

def update_user_profile_sync(chat_id, field_values):
    try:
        from sheets_core import update_user_profile_data
        debug_log(f"Updating profile for user {chat_id} with auto-summary generation", "SheetsLogger")
        return update_user_profile_data(chat_id, field_values)
    except Exception as e:
        debug_log(f"Error updating profile: {e}", "SheetsLogger")
        return False

def log_gpt_usage_to_file(message_id, chat_id, main_usage, summary_usage, extract_usage, gpt_d_usage, gpt_e_usage, total_cost_ils):
    try:
        from utils import get_israel_time
        log_entry = {
            "timestamp": get_israel_time().isoformat(),
            "interaction_id": message_id,  # שם שהדוח מחפש
            "chat_id": chat_id,
            "type": "gpt_a",  # סוג שהדוח מחפש
            "cost_total_ils": total_cost_ils,  # שם שהדוח מחפש
            "main_usage": main_usage,
            "summary_usage": summary_usage,
            "extract_usage": extract_usage,
            "gpt_d_usage": gpt_d_usage,
            "gpt_e_usage": gpt_e_usage
        }
        
        with open(gpt_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            
        debug_log(f"Logged GPT usage to file for message {message_id}", "SheetsLogger")
        
    except Exception as e:
        debug_log(f"Error logging GPT usage to file: {e}", "SheetsLogger")

# ================================
# 🔄 Async Wrapper Functions
# ================================

async def log_to_sheets_async(priority: str = "normal", **kwargs):
    await sheets_queue_manager.add_operation("log_to_sheets", priority, kwargs)

async def update_user_profile_async(chat_id, field_values, priority: str = "critical"):
    data = {"chat_id": chat_id, "field_values": field_values}
    await sheets_queue_manager.add_operation("update_profile", priority, data)

# -----------------------------------------------------
# 📈 Increment code_try (Async wrapper that returns value)
# -----------------------------------------------------

async def increment_code_try_async(sheet_states, chat_id, priority: str = "normal"):
    """Increments the code_try counter synchronously (non-blocking via thread)
    so that the caller immediately gets the new attempt number back. We also
    enqueue the operation for the queue to keep the existing batching / rate
    limiting behaviour for the actual Sheet write as a fallback."""

    from sheets_core import increment_code_try_sync  # imported here to avoid circular deps

    # 1️⃣ Run the increment in a worker thread and await the result so we can
    #    respond right away with the updated attempt number.
    new_attempt_val = await asyncio.to_thread(increment_code_try_sync, sheet_states, chat_id)

    return new_attempt_val 