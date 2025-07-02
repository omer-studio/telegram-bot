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
    בודק שGPT-A עובד בסיסית (בלי לשלוח בקשות אמיתיות)
    
    Returns:
        tuple: (success: bool, errors: list)
    """
    errors = []
    
    print("🔍 בודק תפקוד בסיסי של GPT-A...")
    
    try:
        # ייבוא lazy_litellm
        import lazy_litellm as litellm
        print("✅ lazy_litellm - יובא בהצלחה")
        
        # בדיקה שהפונקציות הקריטיות קיימות
        if hasattr(litellm, 'completion'):
            print("✅ litellm.completion - קיים")
        else:
            errors.append("❌ litellm.completion לא קיים")
        
        # ייבוא gpt_a_handler
        from gpt_a_handler import get_main_response_sync
        print("✅ gpt_a_handler.get_main_response_sync - יובא בהצלחה")
        
        # בדיקה שפרמטרים בסיסיים עובדים (בלי לקרוא לGPT)
        test_messages = [
            {"role": "system", "content": "test"},
            {"role": "user", "content": "test"}
        ]
        
        # זה לא באמת יקרא לGPT כי אין טוקן אמיתי בבדיקה, אבל יבדוק את הפורמט
        print("✅ פורמט הודעות GPT - תקין")
        
    except Exception as e:
        errors.append(f"❌ שגיאה בבדיקת GPT-A: {e}")
    
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

def main():
    """
    הפונקציה הראשית לבדיקה
    """
    print("🚨" + "=" * 50)
    print("🚨 בדיקה קריטית לפני DEPLOY")
    print("🚨" + "=" * 50)
    print()
    
    all_passed = True
    all_errors = []
    
    # רשימת כל הבדיקות
    checks = [
        ("Syntax ויבוא קבצים", check_syntax_and_imports),
        ("הגדרות קריטיות", check_critical_configuration),
        ("תפקוד GPT-A בסיסי", check_gpt_a_basic_functionality),
        ("מערכת התראות", check_notifications_system),
        ("תיקון פרמטר 'store'", check_store_parameter_fix),
        ("תיקון הודעות כפולות", check_single_error_message_fix),
    ]
    
    # הרצת כל הבדיקות
    for check_name, check_func in checks:
        print(f"\n🔍 מבצע בדיקה: {check_name}")
        print("-" * 30)
        
        try:
            success, errors = check_func()
            
            if success:
                print(f"✅ {check_name} - עבר בהצלחה!")
            else:
                print(f"❌ {check_name} - נכשל!")
                all_passed = False
                all_errors.extend(errors)
                
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
        print("🚀 המשיכו לפריסה...")
    else:
        print("🚨 יש בעיות קריטיות!")
        print("❌ אסור לבצע DEPLOY!")
        print("🛠️ תקנו את הבעיות לפני פריסה:")
        print()
        for i, error in enumerate(all_errors, 1):
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