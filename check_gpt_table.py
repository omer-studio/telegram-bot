#!/usr/bin/env python3
"""
בדיקה פשוטה של טבלת gpt_calls_log
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os

def check_gpt_table():
    try:
        # 🔧 תיקון מערכתי: שימוש ב-get_config() מרכזי במקום קריאה קשיחה
        try:
            from config import get_config
            config = get_config()
            db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        except Exception:
            # fallback למשתנה סביבה אם get_config() נכשל
            db_url = os.getenv("DATABASE_URL")
        
        if not db_url:
            print("❌ לא נמצא URL למסד הנתונים")
            return
        
        print(f"🔗 מתחבר למסד הנתונים...")
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        
        # בדיקה אם הטבלה קיימת
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'gpt_calls_log'
            );
        """)
        table_exists = cursor.fetchone()[0]
        print(f"📊 טבלת gpt_calls_log קיימת: {table_exists}")
        
        if not table_exists:
            print("❌ הטבלה לא קיימת!")
            return
        
        # ספירת שורות
        cursor.execute("SELECT COUNT(*) FROM gpt_calls_log;")
        count = cursor.fetchone()[0]
        print(f"📈 מספר שורות בטבלה: {count}")
        
        if count == 0:
            print("⚠️ הטבלה ריקה!")
            return
        
        # הצגת 3 שורות האחרונות
        cursor.execute("""
            SELECT 
                timestamp,
                call_type,
                chat_id,
                tokens_input,
                tokens_output,
                cost_usd
            FROM gpt_calls_log
            ORDER BY timestamp DESC
            LIMIT 3;
        """)
        
        rows = cursor.fetchall()
        print(f"\n📋 3 השורות האחרונות:")
        for i, row in enumerate(rows, 1):
            print(f"  {i}. {row['timestamp']} | {row['call_type']} | chat:{row['chat_id']} | tokens:{row['tokens_input']}+{row['tokens_output']} | cost:{row['cost_usd']}")
        
        cursor.close()
        connection.close()
        print("✅ בדיקה הושלמה!")
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_gpt_table() 