#!/usr/bin/env python3
"""
🎯 SYSTEM MANAGER - מרכז בקרה מערכתי
=====================================

מטרה: מקום אחד לכל הגדרות המערכת
עקרון: פשוט, ברור, נגיש למי שלא מבין בקוד

במקום שכל קובץ יחפש config.json במקום אחר,
כל הקוד עובר דרך הקבצים הזה.

אם יש בעיה - הודעת שגיאה ברורה בעברית עם הוראות מדויקות.
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from datetime import datetime

# 🎯 הגדרות בסיסיות
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_NAME = "config.json"
CONFIG_DIR_NAME = "etc/secrets"

class SystemConfigError(Exception):
    """שגיאה בהגדרות המערכת - עם הודעות ברורות למשתמש"""
    
    def __init__(self, problem: str, solution: str, technical_details: str = ""):
        self.problem = problem
        self.solution = solution
        self.technical_details = technical_details
        
        # הודעה ברורה למשתמש
        message = f"""
❌ בעיה במערכת: {problem}

💡 פתרון:
{solution}

⏰ זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
"""
        if technical_details:
            message += f"\n🔧 פרטים טכניים: {technical_details}"
        
        super().__init__(message)

class SystemManager:
    """מנהל מערכת - מקום אחד לכל הגדרות המערכת"""
    
    def __init__(self):
        self._config = None
        self._config_path = None
        self._last_loaded = None
        
    def _find_config_file(self) -> str:
        """מוצא את קובץ הקונפיגורציה - עם הודעות ברורות אם לא נמצא"""
        
        # 1. בדיקת משתנה סביבה
        env_path = os.getenv("CONFIG_PATH")
        if env_path and os.path.exists(env_path):
            return env_path
        
        # 2. בדיקת נתיבים סטנדרטיים
        possible_paths = [
            os.path.join(PROJECT_ROOT, CONFIG_DIR_NAME, CONFIG_FILE_NAME),  # נתיב מקומי
            f"/etc/secrets/{CONFIG_FILE_NAME}",  # נתיב שרת Linux
            f"etc/secrets/{CONFIG_FILE_NAME}",   # נתיב יחסי
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # 3. אם לא נמצא - יצירת קובץ ברירת מחדל
        return self._create_default_config()
    
    def _create_default_config(self) -> str:
        """יוצר קובץ קונפיגורציה ברירת מחדל עם הוראות ברורות"""
        
        default_path = os.path.join(PROJECT_ROOT, CONFIG_DIR_NAME, CONFIG_FILE_NAME)
        
        # יצירת התיקייה אם לא קיימת
        os.makedirs(os.path.dirname(default_path), exist_ok=True)
        
        # תוכן ברירת מחדל עם הסברים
        default_config = {
            "_README": "קובץ הגדרות המערכת - אנא מלא את הערכים הנדרשים",
            "_INSTRUCTIONS": {
                "1": "קבל TELEGRAM_BOT_TOKEN מ-@BotFather בטלגרם",
                "2": "קבל OPENAI_API_KEY מ-https://platform.openai.com/api-keys",
                "3": "קבל GEMINI_API_KEY מ-https://makersuite.google.com/app/apikey",
                "4": "קבל RENDER_API_KEY מ-https://dashboard.render.com/",
                "5": "מצא RENDER_SERVICE_ID בכתובת URL של השירות ברנדר"
            },
            "TELEGRAM_BOT_TOKEN": "BOT_TOKEN_HERE",
            "OPENAI_API_KEY": "OPENAI_KEY_HERE", 
            "OPENAI_ADMIN_KEY": "ADMIN_KEY_HERE",
            "GEMINI_API_KEY": "GEMINI_KEY_HERE",
            "RENDER_API_KEY": "RENDER_KEY_HERE",
            "RENDER_SERVICE_ID": "RENDER_SERVICE_ID_HERE",
            "DATABASE_URL": "DATABASE_URL_HERE",
            "DATABASE_EXTERNAL_URL": "DATABASE_EXTERNAL_URL_HERE"
        }
        
        try:
            with open(default_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            
            raise SystemConfigError(
                problem="קובץ הגדרות חסר",
                solution=f"""
1. פתח את הקובץ: {default_path}
2. מלא את הערכים הנדרשים (החלף את ה-HERE בערכים האמיתיים)
3. שמור את הקובץ
4. הפעל שוב את המערכת
                """,
                technical_details=f"נוצר קובץ ברירת מחדל ב-{default_path}"
            )
            
        except Exception as e:
            raise SystemConfigError(
                problem="לא ניתן ליצור קובץ הגדרות",
                solution=f"""
1. וודא שיש הרשאות כתיבה לתיקייה: {os.path.dirname(default_path)}
2. צור את התיקייה ידנית אם היא לא קיימת
3. צור קובץ {CONFIG_FILE_NAME} עם הגדרות בסיסיות
                """,
                technical_details=str(e)
            )
    
    def _load_config(self) -> Dict[str, Any]:
        """טוען את קובץ הקונפיגורציה עם בדיקות תקינות"""
        
        config_path = self._find_config_file()
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # בדיקת תקינות בסיסית
            self._validate_config(config)
            
            self._config_path = config_path
            self._last_loaded = datetime.now()
            
            return config
            
        except json.JSONDecodeError as e:
            raise SystemConfigError(
                problem="קובץ הגדרות פגום",
                solution=f"""
1. פתח את הקובץ: {config_path}
2. בדוק שהפורמט JSON תקין (אין פסיקים מיותרים, סוגריים סגורים)
3. השתמש בכלי בדיקת JSON אונליין אם צריך
4. שמור ונסה שוב
                """,
                technical_details=f"JSON Error: {e}"
            )
        except Exception as e:
            raise SystemConfigError(
                problem="לא ניתן לקרוא קובץ הגדרות",
                solution=f"""
1. וודא שהקובץ קיים: {config_path}
2. וודא שיש הרשאות קריאה
3. בדוק שהקובץ לא פגום
                """,
                technical_details=str(e)
            )
    
    def _validate_config(self, config: Dict[str, Any]) -> None:
        """בודק שהקונפיגורציה תקינה"""
        
        required_keys = [
            "TELEGRAM_BOT_TOKEN",
            "OPENAI_API_KEY", 
            "DATABASE_URL"
        ]
        
        missing_keys = []
        invalid_keys = []
        
        for key in required_keys:
            if key not in config:
                missing_keys.append(key)
            elif not config[key] or config[key].endswith("_HERE"):
                invalid_keys.append(key)
        
        if missing_keys or invalid_keys:
            problem_parts = []
            solution_parts = []
            
            if missing_keys:
                problem_parts.append(f"שדות חסרים: {', '.join(missing_keys)}")
                solution_parts.append(f"הוסף את השדות החסרים: {', '.join(missing_keys)}")
            
            if invalid_keys:
                problem_parts.append(f"שדות לא מוגדרים: {', '.join(invalid_keys)}")
                solution_parts.append(f"מלא את הערכים האמיתיים עבור: {', '.join(invalid_keys)}")
            
            raise SystemConfigError(
                problem=" | ".join(problem_parts),
                solution=f"""
1. פתח את הקובץ: {self._config_path or 'קובץ הגדרות'}
2. {' | '.join(solution_parts)}
3. שמור את הקובץ
4. הפעל שוב את המערכת
                """
            )
    
    def get_config(self) -> Dict[str, Any]:
        """מחזיר את הקונפיגורציה - טוען מחדש אם צריך"""
        
        if self._config is None:
            self._config = self._load_config()
        
        return self._config
    
    def reload_config(self) -> Dict[str, Any]:
        """טוען מחדש את הקונפיגורציה"""
        
        self._config = None
        return self.get_config()
    
    # 🎯 פונקציות נוחות לגישה לערכים ספציפיים
    
    def get_telegram_token(self) -> str:
        """מחזיר טוקן טלגרם"""
        config = self.get_config()
        token = config.get("TELEGRAM_BOT_TOKEN")
        
        if not token or token == "BOT_TOKEN_HERE":
            raise SystemConfigError(
                problem="טוקן טלגרם חסר",
                solution="""
1. לך ל-@BotFather בטלגרם
2. צור בוט חדש או קבל טוקן לבוט קיים
3. העתק את הטוקן לקובץ הגדרות במקום BOT_TOKEN_HERE
4. שמור והפעל שוב
                """
            )
        
        return token
    
    def get_openai_key(self) -> str:
        """מחזיר מפתח OpenAI"""
        config = self.get_config()
        key = config.get("OPENAI_API_KEY") or config.get("OPENAI_ADMIN_KEY")
        
        if not key or key.endswith("_HERE"):
            raise SystemConfigError(
                problem="מפתח OpenAI חסר",
                solution="""
1. לך ל-https://platform.openai.com/api-keys
2. צור מפתח חדש
3. העתק את המפתח לקובץ הגדרות במקום OPENAI_KEY_HERE
4. שמור והפעל שוב
                """
            )
        
        return key
    
    def get_database_url(self) -> str:
        """מחזיר כתובת מסד הנתונים"""
        config = self.get_config()
        url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        if not url or url.endswith("_HERE"):
            raise SystemConfigError(
                problem="כתובת מסד נתונים חסרה",
                solution="""
1. קבל כתובת מסד נתונים מספק השירות (Render/Heroku/אחר)
2. העתק את הכתובת לקובץ הגדרות במקום DATABASE_URL_HERE
3. שמור והפעל שוב
                """
            )
        
        return url
    
    def get_render_api_key(self) -> str:
        """מחזיר מפתח Render API"""
        config = self.get_config()
        key = config.get("RENDER_API_KEY")
        
        if not key or key.endswith("_HERE"):
            raise SystemConfigError(
                problem="מפתח Render חסר",
                solution="""
1. לך ל-https://dashboard.render.com/
2. לך ל-Account Settings -> API Keys
3. צור מפתח חדש
4. העתק את המפתח לקובץ הגדרות במקום RENDER_KEY_HERE
5. שמור והפעל שוב
                """
            )
        
        return key
    
    def get_render_service_id(self) -> str:
        """מחזיר מזהה שירות Render"""
        config = self.get_config()
        service_id = config.get("RENDER_SERVICE_ID")
        
        if not service_id or service_id.endswith("_HERE"):
            raise SystemConfigError(
                problem="מזהה שירות Render חסר",
                solution="""
1. לך ל-https://dashboard.render.com/
2. בחר את השירות שלך
3. העתק את המזהה מהכתובת URL (srv-xxxxx)
4. הכנס את המזהה לקובץ הגדרות במקום RENDER_SERVICE_ID_HERE
5. שמור והפעל שוב
                """
            )
        
        return service_id
    
    def get_gemini_key(self) -> Optional[str]:
        """מחזיר מפתח Gemini (אופציונלי)"""
        config = self.get_config()
        key = config.get("GEMINI_API_KEY")
        
        if not key or key.endswith("_HERE"):
            return None
        
        return key
    
    def get_config_info(self) -> Dict[str, Any]:
        """מחזיר מידע על הקונפיגורציה"""
        return {
            "config_path": self._config_path,
            "last_loaded": self._last_loaded.isoformat() if self._last_loaded else None,
            "keys_configured": {
                "telegram": bool(self.get_config().get("TELEGRAM_BOT_TOKEN", "").replace("BOT_TOKEN_HERE", "")),
                "openai": bool(self.get_config().get("OPENAI_API_KEY", "").replace("OPENAI_KEY_HERE", "")),
                "database": bool(self.get_config().get("DATABASE_URL", "").replace("DATABASE_URL_HERE", "")),
                "render": bool(self.get_config().get("RENDER_API_KEY", "").replace("RENDER_KEY_HERE", "")),
                "gemini": bool(self.get_config().get("GEMINI_API_KEY", "").replace("GEMINI_KEY_HERE", ""))
            }
        }

# 🎯 Instance גלובלי - מקום אחד לכל המערכת
system_manager = SystemManager()

# 🎯 פונקציות נוחות לשימוש מהיר
def get_config() -> Dict[str, Any]:
    """פונקציה נוחה לקבלת הקונפיגורציה"""
    return system_manager.get_config()

def get_telegram_token() -> str:
    """פונקציה נוחה לקבלת טוקן טלגרם"""
    return system_manager.get_telegram_token()

def get_openai_key() -> str:
    """פונקציה נוחה לקבלת מפתח OpenAI"""
    return system_manager.get_openai_key()

def get_database_url() -> str:
    """פונקציה נוחה לקבלת כתובת מסד נתונים"""
    return system_manager.get_database_url()

def get_render_api_key() -> str:
    """פונקציה נוחה לקבלת מפתח Render"""
    return system_manager.get_render_api_key()

def get_render_service_id() -> str:
    """פונקציה נוחה לקבלת מזהה שירות Render"""
    return system_manager.get_render_service_id()

def get_gemini_key() -> Optional[str]:
    """פונקציה נוחה לקבלת מפתח Gemini"""
    return system_manager.get_gemini_key()

# 🎯 פונקציה לבדיקת תקינות המערכת
def check_system_health() -> Dict[str, Any]:
    """בודק את תקינות המערכת - מחזיר דוח מפורט"""
    
    try:
        info = system_manager.get_config_info()
        
        # בדיקת חיבור למסד נתונים
        try:
            import psycopg2
            db_url = get_database_url()
            conn = psycopg2.connect(db_url)
            conn.close()
            info["database_connection"] = "✅ תקין"
        except Exception as e:
            info["database_connection"] = f"❌ שגיאה: {e}"
        
        # בדיקת קבצים קריטיים
        critical_files = ["main.py", "bot_setup.py", "message_handler.py"]
        info["critical_files"] = {}
        
        for file in critical_files:
            if os.path.exists(file):
                info["critical_files"][file] = "✅ קיים"
            else:
                info["critical_files"][file] = "❌ חסר"
        
        return info
        
    except Exception as e:
        return {
            "error": str(e),
            "status": "❌ שגיאה במערכת"
        }

if __name__ == "__main__":
    # בדיקה עצמית
    print("🎯 SYSTEM MANAGER - בדיקה עצמית")
    print("=" * 50)
    
    try:
        health = check_system_health()
        print(json.dumps(health, indent=2, ensure_ascii=False))
        print("\n✅ המערכת תקינה!")
        
    except SystemConfigError as e:
        print(f"\n❌ שגיאה במערכת:\n{e}")
        
    except Exception as e:
        print(f"\n💥 שגיאה לא צפויה: {e}") 