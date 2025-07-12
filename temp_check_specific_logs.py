#!/usr/bin/env python3
"""
בדיקה האם הלוגים הספציפיים שהמשתמש הראה נשמרים
"""
import os
import sys
import psycopg2
from datetime import datetime, timedelta

def check_specific_logs():
    """בדיקה ללוגים מספציפיים מהדוגמה"""
    try:
        # חיבור למסד הנתונים
        from config import DB_URL
        database_url = DB_URL
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # חיפוש לוגים עם מילות מפתח מהדוגמה
        search_terms = [
            "GPT-A before_gpt_call",
            "LiteLLM completion()",
            "gemini-2.5-flash",
            "calculate_gpt_cost CALLED",
            "log_gpt_call",
            "GPT_JSONL_LOGGER",
            "TELEGRAM_REPLY",
            "SENT] הודעה נשלחה",
            "BACKGROUND] כל משימות הרקע הושלמו",
            "InteractionsLogger",
            "ADMIN_NOTIFICATION"
        ]
        
        print("🔍 בדיקה של לוגים ספציפיים מהדוגמה...")
        
        for term in search_terms:
            cursor.execute("""
                SELECT COUNT(*) FROM deployment_logs 
                WHERE message LIKE %s
                AND created_at >= NOW() - INTERVAL '1 hour'
            """, (f'%{term}%',))
            count = cursor.fetchone()[0]
            
            if count > 0:
                print(f"✅ '{term}': {count} רשומות")
                
                # הצגת דוגמה
                cursor.execute("""
                    SELECT created_at, LEFT(message, 150) 
                    FROM deployment_logs 
                    WHERE message LIKE %s
                    AND created_at >= NOW() - INTERVAL '1 hour'
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (f'%{term}%',))
                sample = cursor.fetchone()
                if sample:
                    print(f"   דוגמה: {sample[0]} | {sample[1]}...")
            else:
                print(f"❌ '{term}': לא נמצא")
            
            print()
        
        # בדיקה מיוחדת ללוגים של GPT
        print("🤖 בדיקה מיוחדת ללוגים של GPT:")
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE (message LIKE '%GPT%' OR message LIKE '%gemini%')
            AND created_at >= NOW() - INTERVAL '1 hour'
        """)
        gpt_count = cursor.fetchone()[0]
        print(f"📊 לוגים הקשורים ל-GPT: {gpt_count}")
        
        # בדיקה מיוחדת ללוגים של טלגרם
        print("\n📱 בדיקה מיוחדת ללוגים של טלגרם:")
        cursor.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE (message LIKE '%telegram%' OR message LIKE '%TELEGRAM%')
            AND created_at >= NOW() - INTERVAL '1 hour'
        """)
        telegram_count = cursor.fetchone()[0]
        print(f"📊 לוגים הקשורים לטלגרם: {telegram_count}")
        
        # דוגמאות אחרונות
        print("\n🎯 דוגמאות מהלוגים האחרונים:")
        cursor.execute("""
            SELECT created_at, LEFT(message, 200) 
            FROM deployment_logs 
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            ORDER BY created_at DESC
            LIMIT 10
        """)
        recent_logs = cursor.fetchall()
        
        for log in recent_logs:
            print(f"  {log[0]} | {log[1]}...")
        
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        return False

if __name__ == "__main__":
    print("🔍 בדיקת לוגים ספציפיים מהדוגמה...")
    success = check_specific_logs()
    
    if success:
        print("\n✅ הבדיקה הסתיימה בהצלחה")
    else:
        print("\n❌ הבדיקה נכשלה") 