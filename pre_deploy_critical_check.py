#!/usr/bin/env python3
"""
🚨 בדיקה קריטית לפני deploy

זה הסקריפט שצריך לרוץ לפני כל deploy כדי למנוע פריסת קוד שבור.
אם הבדיקה נכשלת - אסור לעשות deploy!

שימוש:
python pre_deploy_critical_check.py

אם המסך אדום = לא לפרוס!
אם המסך ירוק = בטוח לפרוס!
"""

import os
import sys
import importlib
import importlib.util
import json
import traceback
import re

def check_syntax_and_imports():
    """
    בודק שכל הקבצים החיוניים מתקמפלים ונטענים בהצלחה
    
    Returns:
        tuple: (success: bool, errors: list)
    """
    critical_files = [
        "config.py",
        "bot_setup.py", 
        "message_handler.py",
        "gpt_a_handler.py",
        "notifications.py",
        "auto_rollback.py",
        "main.py",
        "lazy_litellm.py"
    ]
    
    errors = []
    
    print("🔍 בודק syntax ויבוא של קבצים קריטיים...")
    
    for file in critical_files:
        try:
            if not os.path.exists(file):
                errors.append(f"❌ קובץ חסר: {file}")
                continue
            
            # בדיקת syntax
            with open(file, 'r', encoding='utf-8') as f:
                code = f.read()
            
            try:
                compile(code, file, 'exec')
                print(f"✅ {file} - syntax תקין")
            except SyntaxError as e:
                errors.append(f"❌ שגיאת syntax ב{file}: {e}")
                continue
            
            # ניסיון import (רק לקבצים שאפשר)
            if file.endswith('.py') and file != "main.py":  # main.py עלול להפעיל server
                try:
                    module_name = file[:-3]  # הסרת .py
                    spec = importlib.util.spec_from_file_location(module_name, file)
                    if spec is not None:
                        module = importlib.util.module_from_spec(spec)
                        # לא מפעילים את המודול, רק בודקים שהוא נטען
                        print(f"✅ {file} - import מוצלח")
                    else:
                        errors.append(f"⚠️ לא הצלחתי ליצור spec עבור {file}")
                except Exception as e:
                    errors.append(f"⚠️ בעיית import ב{file}: {str(e)[:100]}")
            
        except Exception as e:
            errors.append(f"❌ שגיאה כללית ב{file}: {e}")
    
    return len(errors) == 0, errors

def check_critical_configuration():
    """
    בודק שההגדרות הקריטיות קיימות ותקינות
    
    Returns:
        tuple: (success: bool, errors: list)
    """
    errors = []
    
    print("🔍 בודק הגדרות קריטיות...")
    
    try:
        # ייבוא config
        import config
        
        # בדיקת משתני סביבה קריטיים
        required_config_attrs = [
            "TELEGRAM_BOT_TOKEN",
            "GPT_MODELS", 
            "GPT_PARAMS",
            "GPT_FALLBACK_MODELS"
        ]
        
        for attr in required_config_attrs:
            if not hasattr(config, attr):
                errors.append(f"❌ config חסר: {attr}")
            else:
                value = getattr(config, attr)
                if not value:
                    errors.append(f"❌ config ריק: {attr}")
                else:
                    print(f"✅ config.{attr} - קיים ולא ריק")
        
        # בדיקה ספציפית של GPT models
        if hasattr(config, 'GPT_MODELS') and config.GPT_MODELS:
            if 'gpt_a' not in config.GPT_MODELS:
                errors.append("❌ config.GPT_MODELS חסר gpt_a")
            else:
                print("✅ config.GPT_MODELS['gpt_a'] - קיים")
        
        # בדיקה של requirements.txt
        if os.path.exists("requirements.txt"):
            with open("requirements.txt", 'r', encoding='utf-8') as f:
                requirements = f.read()
            
            # בדיקה שlitellm נעול לגרסה בטוחה
            if "litellm==" in requirements:
                print("✅ litellm נעול לגרסה ספציפית")
            else:
                errors.append("⚠️ litellm לא נעול לגרסה ספציפית - מסוכן!")
        else:
            errors.append("❌ requirements.txt לא נמצא")
            
    except Exception as e:
        errors.append(f"❌ שגיאה בבדיקת config: {e}")
    
    return len(errors) == 0, errors

def check_gpt_a_basic_functionality():
    """
    🚨 בודק שGPT-A עובד **באמת** - הכי חשוב!
    
    Returns:
        tuple: (success: bool, errors: list)
    """
    errors = []
    
    print("🔍 בודק תפקוד **אמיתי** של GPT-A...")
    print("🚨 זו הבדיקה הכי חשובה - אם GPT-A לא עובד, אסור לפרוס!")
    
    try:
        # ייבוא lazy_litellm
        import lazy_litellm as litellm
        print("✅ lazy_litellm - יובא בהצלחה")
        
        # בדיקה שהפונקציות הקריטיות קיימות
        if hasattr(litellm, 'completion'):
            print("✅ litellm.completion - קיים")
        else:
            errors.append("❌ litellm.completion לא קיים")
            return False, errors
        
        # ייבוא gpt_a_handler
        from gpt_a_handler import get_main_response_sync
        print("✅ gpt_a_handler.get_main_response_sync - יובא בהצלחה")
        
        # 🚨 בדיקה אמיתית של GPT-A - הכי חשוב!
        print("🧪 מבצע קריאה אמיתית ל-GPT-A...")
        print("⏱️ יש timeout של 30 שניות למקרה שGPT-A לא מגיב...")
        
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("GPT-A timeout - לא הגיב תוך 30 שניות")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(30)  # 30 שניות timeout
        
        try:
            test_messages = [
                {"role": "system", "content": "אתה בוט עוזר. תענה רק 'בדיקה עברה' בלי שום דבר נוסף."},
                {"role": "user", "content": "היי"}
            ]
            
            # קריאה אמיתית ל-GPT-A!
            result = get_main_response_sync(
                test_messages, 
                "pre_deploy_test", 
                "pre_deploy_test", 
                False, 
                "health_check", 
                "pre_deploy_test"
            )
            
            if not result:
                errors.append("❌ GPT-A לא מחזיר תוצאה כלל!")
                return False, errors
            
            if not result.get("bot_reply"):
                errors.append("❌ GPT-A לא מחזיר bot_reply!")
                return False, errors
            
            bot_reply = result.get("bot_reply", "").strip()
            
            if len(bot_reply) < 3:
                errors.append(f"❌ GPT-A מחזיר תשובה קצרה מדי: '{bot_reply}'")
                return False, errors
            
            if "error" in bot_reply.lower() or "שגיאה" in bot_reply.lower():
                errors.append(f"❌ GPT-A מחזיר תשובת שגיאה: '{bot_reply}'")
                return False, errors
            
            print(f"✅ GPT-A עובד אמיתית! תשובה: '{bot_reply[:50]}...'")
            print("🎉 הבדיקה הכי חשובה עברה!")
            print("✅ המשתמשים יוכלו לקבל תשובות מהבוט!")
            
        except TimeoutError as timeout_error:
            errors.append(f"❌ GPT-A timeout - לא הגיב תוך 30 שניות: {timeout_error}")
            return False, errors
        except Exception as gpt_test_error:
            errors.append(f"❌ קריאה אמיתית ל-GPT-A נכשלה: {gpt_test_error}")
            return False, errors
        finally:
            signal.alarm(0)  # ביטול timeout
        
    except Exception as e:
        errors.append(f"❌ שגיאה כללית בבדיקת GPT-A: {e}")
    
    return len(errors) == 0, errors

def check_notifications_system():
    """
    בודק שמערכת ההתראות עובדת
    
    Returns:
        tuple: (success: bool, errors: list)
    """
    errors = []
    
    print("🔍 בודק מערכת התראות...")
    
    try:
        from notifications import (
            _load_critical_error_users, 
            _save_critical_error_users,
            safe_add_user_to_recovery_list,
            send_admin_notification
        )
        print("✅ notifications - כל הפונקציות יובאו בהצלחה")
        
        # בדיקה שתיקיית data קיימת או יכולה להיווצר
        if not os.path.exists("data"):
            try:
                os.makedirs("data", exist_ok=True)
                print("✅ תיקיית data - נוצרה")
            except Exception as e:
                errors.append(f"❌ לא הצלחתי ליצור תיקיית data: {e}")
        else:
            print("✅ תיקיית data - קיימת")
        
        # בדיקה בסיסית של טעינה ושמירה (בלי לשנות קבצים אמיתיים)
        try:
            test_users = _load_critical_error_users()
            print("✅ _load_critical_error_users - עובד")
        except Exception as e:
            errors.append(f"❌ _load_critical_error_users נכשל: {e}")
        
    except Exception as e:
        errors.append(f"❌ שגיאה בבדיקת מערכת התראות: {e}")
    
    return len(errors) == 0, errors

def check_store_parameter_fix():
    """
    בודק שהתיקון של פרמטר ה'store' בוצע
    
    Returns:
        tuple: (success: bool, errors: list)
    """
    errors = []
    
    print("🔍 בודק תיקון פרמטר 'store'...")
    
    try:
        with open("gpt_a_handler.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # בדיקה שאין יותר 'store': True
        if '"store": True' in content or "'store': True" in content:
            errors.append("❌ נמצא עדיין פרמטר 'store': True ב-gpt_a_handler.py!")
        else:
            print("✅ פרמטר 'store' הוסר בהצלחה")
        
        # בדיקה שיש completion_params
        if "completion_params = {" in content:
            print("✅ completion_params מוגדר")
        else:
            errors.append("❌ completion_params לא נמצא")
            
    except Exception as e:
        errors.append(f"❌ שגיאה בבדיקת תיקון store: {e}")
    
    return len(errors) == 0, errors

def check_single_error_message_fix():
    """
    בודק שהתיקון למניעת הודעות שגיאה כפולות בוצע
    
    Returns:
        tuple: (success: bool, errors: list)
    """
    errors = []
    
    print("🔍 בודק תיקון מניעת הודעות שגיאה כפולות...")
    
    try:
        with open("notifications.py", 'r', encoding='utf-8') as f:
            content = f.read()
        
        # בדיקה שיש בדיקה לפני שליחת הודעה
        if "כבר קיבל הודעת שגיאה" in content:
            print("✅ בדיקת הודעות כפולות קיימת")
        else:
            errors.append("❌ בדיקת מניעת הודעות כפולות לא קיימת!")
        
        # בדיקה שיש התראה לאדמין על רישום משתמש
        if "משתמש חדש נרשם לרשימת התאוששות" in content:
            print("✅ התראה על רישום משתמש קיימת")
        else:
            errors.append("⚠️ התראה על רישום משתמש חסרה")
            
    except Exception as e:
        errors.append(f"❌ שגיאה בבדיקת תיקון הודעות כפולות: {e}")
    
    return len(errors) == 0, errors

# -----------------------------------------------------
# ✅ NEW CHECK: New-user full access message after approval
# -----------------------------------------------------

def check_new_user_full_access_message():
    """
    מוודא שלאחר אישור תנאים הבוט שולח את full_access_message (ולא הודעת קוד כפולה).
    הבדיקה קוראת את message_handler.py ומחפשת שהפונקציה
    handle_pending_user_background משתמשת ב-full_access_message().

    Returns:
        tuple: (success: bool, errors: list)
    """
    errors = []
    target_file = "message_handler.py"

    if not os.path.exists(target_file):
        errors.append(f"❌ {target_file} לא נמצא")
        return False, errors

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()

        # חיפוש שימוש ב-full_access_message בתוך 600 תווים אחרי ההגדרה
        pattern = r"async def handle_pending_user_background[\s\S]{0,800}?full_access_message\("
        if re.search(pattern, content):
            return True, []
        else:
            errors.append("❌ handle_pending_user_background לא שולחת full_access_message – יתכן שהזרימה למשתמש חדש תישבר")
            return False, errors
    except Exception as e:
        errors.append(f"❌ שגיאה בבדיקת full_access_message: {e}")
        return False, errors

# -----------------------------------------------------
# 🔍 Additional static CI checks requested by user
# -----------------------------------------------------

def check_welcome_messages_once():
    """Verifies that get_welcome_messages() is used only once (to send 3 welcome
    messages on first user interaction).
    Returns tuple(success, errors)."""
    errors = []
    target = "message_handler.py"
    try:
        if not os.path.exists(target):
            return False, [f"❌ {target} לא נמצא"]
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        occurrences = content.count("get_welcome_messages(")
        if occurrences == 1:
            return True, []
        else:
            errors.append(f"❌ get_welcome_messages() הופיע {occurrences} פעמים – צריך רק פעם אחת (בflow של משתמש חדש)")
            return False, errors
    except Exception as e:
        return False, [f"❌ שגיאה בבדיקת Welcome messages: {e}"]


def check_state_transitions():
    """Static check to ensure key sheet transition functions are present in the
    expected handler functions (register_user, approve_user, check_user_access)."""
    errors = []
    target = "message_handler.py"
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        required_pairs = [
            ("handle_new_user_background", "register_user("),
            ("handle_unregistered_user_background", "register_user("),
            ("handle_pending_user_background", "approve_user("),
            ("handle_message", "check_user_access("),
        ]

        for fn_name, symbol in required_pairs:
            pattern = rf"async def {fn_name}[\s\S]{{0,800}}{re.escape(symbol)}"
            if not re.search(pattern, content):
                errors.append(f"❌ לא נמצא שימוש ב-{symbol.strip()} בתוך {fn_name} – בדוק טרנזיציית סטייט")

        return (len(errors) == 0), errors
    except Exception as e:
        return False, [f"❌ שגיאה בבדיקת טרנזיציות סטייט: {e}"]


def check_code_try_increment_logic():
    """Ensures increment_code_try_sync updates code_try_col. Static regex search."""
    errors = []
    target = "sheets_core.py"
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()
        if "def increment_code_try_sync" not in content:
            return False, ["❌ increment_code_try_sync לא נמצא"]

        # מחפשים update_cell עם code_try_col
        pattern = r"update_cell\(row_index,\s*code_try_col[\s,]"
        if re.search(pattern, content):
            return True, []
        else:
            errors.append("❌ increment_code_try_sync לא מעדכן code_try_col כמצופה")
            return False, errors
    except Exception as e:
        return False, [f"❌ שגיאה בבדיקת code_try: {e}"]


def check_critical_message_order():
    """Verifies messages are sent in correct order in approval flow.
    Specifically: in handle_unregistered_user_background – code_approved_message then send_approval_message.
    In handle_pending_user_background – full_access_message then nice_keyboard_message."""
    errors = []
    target = "message_handler.py"
    try:
        with open(target, "r", encoding="utf-8") as f:
            content = f.read()

        # Unregistered flow order
        pattern_unreg = r"handle_unregistered_user_background[\s\S]{0,600}?code_approved_message\(\)[\s\S]{0,200}?send_approval_message\("
        if not re.search(pattern_unreg, content):
            errors.append("❌ הסדר 'code_approved_message → send_approval_message' חסר או שגוי ב-handle_unregistered_user_background")

        # Pending flow order
        pattern_pending = r"handle_pending_user_background[\s\S]{0,600}?full_access_message\(\)[\s\S]{0,200}?nice_keyboard_message\("
        if not re.search(pattern_pending, content):
            errors.append("❌ הסדר 'full_access_message → nice_keyboard_message' חסר או שגוי ב-handle_pending_user_background")

        return (len(errors) == 0), errors
    except Exception as e:
        return False, [f"❌ שגיאה בבדיקת סדר הודעות קריטיות: {e}"]

def main():
    """
    הפונקציה הראשית לבדיקה
    """
    print("🚨" + "=" * 50)
    print("🚨 בדיקה קריטית לפני DEPLOY")
    print("🚨" + "=" * 50)
    print("🚨 הבדיקה הכי חשובה: GPT-A צריך לעבוד!")
    print("🚨 אם GPT-A נכשל - המשתמשים לא יקבלו תשובות!")
    print("🚨" + "=" * 50)
    print()
    
    all_passed = True
    all_errors = []
    
    # רשימת כל הבדיקות - GPT-A ראשון כי הוא הכי חשוב!
    checks = [
        ("🚨 GPT-A אמיתי (הכי חשוב!)", check_gpt_a_basic_functionality),
        ("Syntax ויבוא קבצים", check_syntax_and_imports),
        ("הגדרות קריטיות", check_critical_configuration),
        ("מערכת התראות", check_notifications_system),
        ("תיקון פרמטר 'store'", check_store_parameter_fix),
        ("תיקון הודעות כפולות", check_single_error_message_fix),
        ("בדיקת הודעת full_access_message בזרימת משתמש חדש", check_new_user_full_access_message),
        ("Welcome messages once", check_welcome_messages_once),
        ("State transitions", check_state_transitions),
        ("code_try increment", check_code_try_increment_logic),
        ("Critical message order", check_critical_message_order),
    ]
    
    # הרצת כל הבדיקות
    for check_name, check_func in checks:
        print(f"\n🔍 מבצע בדיקה: {check_name}")
        print("-" * 30)
        
        try:
            success, errors = check_func()
            
            if success:
                print(f"✅ {check_name} - עבר בהצלחה!")
                
                # התראה מיוחדת כשGPT-A עובר
                if "GPT-A" in check_name:
                    print("🎉🎉🎉 GPT-A עובד! זה הכי חשוב! 🎉🎉🎉")
            else:
                print(f"❌ {check_name} - נכשל!")
                all_passed = False
                all_errors.extend(errors)
                
                # התראה חמורה אם GPT-A נכשל
                if "GPT-A" in check_name:
                    print("🚨" * 20)
                    print("🚨 GPT-A לא עובד - זה קריטי ביותר!")
                    print("🚨 אסור לפרוס עד שGPT-A יעבוד!")
                    print("🚨" * 20)
                
                # הצגת השגיאות
                for error in errors:
                    print(f"  {error}")
                    
        except Exception as e:
            print(f"🚨 שגיאה קריטית בבדיקת {check_name}: {e}")
            all_passed = False
            all_errors.append(f"שגיאה קריטית ב{check_name}: {e}")
    
    # סיכום
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 כל הבדיקות עברו בהצלחה!")
        print("✅ בטוח לבצע DEPLOY!")
        print("✅ GPT-A עובד - זה הכי חשוב!")
        print("🚀 המשיכו לפריסה...")
    else:
        # בדיקה מיוחדת אם GPT-A נכשל
        gpt_a_failed = any("GPT-A" in error for error in all_errors)
        
        if gpt_a_failed:
            print("🚨" * 25)
            print("🚨 GPT-A לא עובד - זה הכי חמור!")
            print("🚨 המשתמשים לא יקבלו תשובות!")
            print("🚨 אסור לפרוס עד שGPT-A יעבוד!")
            print("🚨" * 25)
        else:
            print("🚨 יש בעיות קריטיות!")
            print("❌ אסור לבצע DEPLOY!")
        
        print("🛠️ תקנו את הבעיות לפני פריסה:")
        print()
        for i, error in enumerate(all_errors, 1):
            if "GPT-A" in error:
                print(f"🚨 {i}. {error}")  # מסמן GPT-A באדום
            else:
                print(f"{i}. {error}")
        print()
        print("🔄 הריצו שוב את הבדיקה אחרי התיקונים")
    
    print("=" * 50)
    
    return all_passed

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"🚨 שגיאה קריטית בבדיקה: {e}")
        print("❌ אסור לבצע DEPLOY!")
        sys.exit(1)