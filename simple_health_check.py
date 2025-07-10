#!/usr/bin/env python3
"""
🩺 בדיקת בריאות מערכת פשוטה
4 בדיקות בסיסיות בלבד - לא overengineering
"""

from simple_logger import logger

def check_config():
    """בדיקה 1: קובץ config.json נגיש"""
    try:
        from config import get_config
        config = get_config()
        return config.get("TELEGRAM_BOT_TOKEN") is not None
    except Exception as e:
        print(f"❌ Config: {e}")
        return False

def check_database():
    """בדיקה 2: מסד נתונים מחובר"""
    try:
        from simple_data_manager import DataManager
        data_manager = DataManager()
        # בדיקה פשוטה של חיבור
        result = data_manager.execute_query("SELECT 1 as test")
        return result is not None
    except Exception as e:
        logger.error(f"Database check failed: {e}")
        print(f"❌ Database: {e}")
        return False

def check_chat_id_handling():
    """בדיקה 3: chat_id מטופל נכון"""
    try:
        from utils import safe_str
        # בדיקות בסיסיות
        assert safe_str(123) == "123"
        assert safe_str("456") == "456"
        try:
            safe_str(None)
            return False  # אמור לזרוק שגיאה
        except ValueError:
            pass  # זה מה שאנחנו רוצים
        return True
    except Exception as e:
        logger.error(f"chat_id check failed: {e}")
        print(f"❌ chat_id: {e}")
        return False

def check_imports():
    """בדיקה 4: import בסיסיים עובדים"""
    try:
        import config
        from utils import safe_str
        # בדיקה פשוטה
        test_result = safe_str("123")
        return test_result == "123"
    except Exception as e:
        logger.error(f"imports check failed: {e}")
        print(f"❌ Imports: {e}")
        return False

def main():
    """הרצת כל הבדיקות"""
    logger.info("מתחיל בדיקת בריאות מערכת")
    checks = [
        ("Config", check_config),
        ("Database", check_database), 
        ("chat_id", check_chat_id_handling),
        ("Imports", check_imports)
    ]
    
    results = []
    for name, check_func in checks:
        result = check_func()
        status = "✅" if result else "❌"
        logger.info(f"בדיקת {name}: {'תקין' if result else 'נכשל'}")
        print(f"{status} {name}")
        results.append(result)
    
    score = sum(results)
    logger.info(f"תוצאה סופית: {score}/4")
    print(f"\n📊 תוצאה: {score}/4 ({score*25}%)")
    
    if score == 4:
        logger.info("המערכת תקינה")
        print("🎉 המערכת תקינה!")
        return True
    else:
        logger.warning("יש בעיות שצריך לטפל בהן")
        print("⚠️ יש בעיות שצריך לטפל בהן")
        return False

if __name__ == "__main__":
    main() 