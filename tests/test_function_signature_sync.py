"""
🔍 בדיקת סנכרון חתימות פונקציות
בודק שהבדיקות מעודכנות עם השינויים בקוד
"""

import inspect
import importlib
import sys
import os
from typing import Dict, List, Tuple

# הוספת הנתיב הנוכחי למסלול הייבוא
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

def get_function_signature(module_name: str, function_name: str) -> str:
    """מחזיר את שמות וסדר הפרמטרים של פונקציה"""
    try:
        module = importlib.import_module(module_name)
        func = getattr(module, function_name)
        sig = inspect.signature(func)
        param_names = [p.name for p in sig.parameters.values()]
        return str(param_names)
    except (ImportError, AttributeError):
        return "NOT_FOUND"

def check_function_signatures() -> Dict[str, List[str]]:
    """בודק סנכרון בין פונקציות בקוד לבדיקות (שמות וסדר פרמטרים בלבד)"""
    
    # פונקציות חשובות לבדיקה - שמות וסדר בלבד
    critical_functions = {
        "message_handler": {
            "handle_background_tasks": ["update", "context", "chat_id", "user_msg", "bot_reply", "message_id", "user_request_start_time", "gpt_result", "history_messages", "messages_for_gpt", "user_response_actual_time"],
            "handle_message": ["update", "context"],
            "run_background_processors": ["chat_id", "user_msg", "bot_reply"]
        },
        "notifications": {
            "send_admin_notification_raw": ["message"],
            "send_error_notification": ["error_message", "chat_id", "user_msg", "error_type"]
        }
    }
    
    issues = []
    
    for module_name, functions in critical_functions.items():
        for func_name, expected_params in functions.items():
            actual_params = get_function_signature(module_name, func_name)
            if actual_params == "NOT_FOUND":
                issues.append(f"❌ {module_name}.{func_name} - לא נמצא!")
            elif actual_params != str(expected_params):
                issues.append(f"⚠️ {module_name}.{func_name} - פרמטרים לא תואמים!")
                issues.append(f"   צפוי: {expected_params}")
                issues.append(f"   בפועל: {actual_params}")
    
    return {"issues": issues}

def test_function_signatures():
    """בדיקה ראשית - רצה לפני כל הבדיקות"""
    print("🔍 בודק סנכרון חתימות פונקציות...")
    
    results = check_function_signatures()
    
    if results["issues"]:
        print("❌ נמצאו בעיות סנכרון:")
        for issue in results["issues"]:
            print(f"   {issue}")
        assert False, "פונקציות לא מסונכרנות - צריך לעדכן בדיקות!"
    else:
        print("✅ כל הפונקציות מסונכרנות!")

if __name__ == "__main__":
    test_function_signatures() 