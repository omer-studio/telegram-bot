import psycopg2
from config import config

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def create_tables():
    """
    יצירת כל הטבלאות הנדרשות במסד הנתונים
    """
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        # כאן יש את כל ה-SQL ליצירת הטבלאות (הועתק מ-db_manager.py)
        # ... existing SQL code ...
        cur.close()
        conn.commit()
        conn.close()
        print("✅ כל הטבלאות נוצרו בהצלחה!")
    except Exception as e:
        print(f"❌ שגיאה ביצירת טבלאות: {e}") 