#!/usr/bin/env python3
"""
🩺 בדיקת בריאות מערכת פשוטה
4 בדיקות בסיסיות בלבד - לא overengineering
"""

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
        import psycopg2
        from config import config
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        if not db_url:
            return False
        conn = psycopg2.connect(db_url)
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database: {e}")
        return False

def check_chat_id_handling():
    """בדיקה 3: chat_id מטופל נכון"""
    try:
        from db_manager import safe_str
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
        print(f"❌ chat_id: {e}")
        return False

def check_imports():
    """בדיקה 4: import בסיסיים עובדים"""
    try:
        import config
        from db_manager import safe_str
        # בדיקה פשוטה
        test_result = safe_str("123")
        return test_result == "123"
    except Exception as e:
        print(f"❌ Imports: {e}")
        return False

def main():
    """הרצת כל הבדיקות"""
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
        print(f"{status} {name}")
        results.append(result)
    
    score = sum(results)
    print(f"\n📊 תוצאה: {score}/4 ({score*25}%)")
    
    if score == 4:
        print("🎉 המערכת תקינה!")
        return True
    else:
        print("⚠️ יש בעיות שצריך לטפל בהן")
        return False

if __name__ == "__main__":
    main() 