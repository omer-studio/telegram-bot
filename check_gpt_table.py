#!/usr/bin/env python3
"""
🔥 בדיקה פשוטה של טבלת interactions_log החדשה
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os

def check_interactions_table():
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
                WHERE table_name = 'interactions_log'
            );
        """)
        table_exists = cursor.fetchone()[0]
        print(f"📊 טבלת interactions_log קיימת: {table_exists}")
        
        if not table_exists:
            print("❌ הטבלה לא קיימת!")
            return
        
        # ספירת שורות
        cursor.execute("SELECT COUNT(*) FROM interactions_log;")
        count = cursor.fetchone()[0]
        print(f"📈 מספר אינטראקציות בטבלה: {count}")
        
        if count == 0:
            print("⚠️ הטבלה ריקה!")
            return
        
        # הצגת 3 אינטראקציות האחרונות
        cursor.execute("""
            SELECT 
                timestamp,
                chat_id,
                user_msg,
                gpt_a_model,
                gpt_a_tokens_input,
                gpt_a_tokens_output,
                total_cost_agorot,
                gpt_b_activated,
                gpt_c_activated,
                gpt_d_activated,
                gpt_e_activated
            FROM interactions_log
            ORDER BY timestamp DESC
            LIMIT 3;
        """)
        
        rows = cursor.fetchall()
        print(f"\n📋 3 האינטראקציות האחרונות:")
        for i, row in enumerate(rows, 1):
            gpts_active = []
            if row['gpt_b_activated']: gpts_active.append('B')
            if row['gpt_c_activated']: gpts_active.append('C') 
            if row['gpt_d_activated']: gpts_active.append('D')
            if row['gpt_e_activated']: gpts_active.append('E')
            
            gpts_str = f"A+{'+'.join(gpts_active)}" if gpts_active else "A"
            user_preview = row['user_msg'][:30] + "..." if len(row['user_msg']) > 30 else row['user_msg']
            
            print(f"  {i}. {row['timestamp']} | chat:{row['chat_id']} | GPTs:{gpts_str}")
            print(f"     User: {user_preview}")
            print(f"     Tokens: {row['gpt_a_tokens_input']}+{row['gpt_a_tokens_output']} | Cost: {row['total_cost_agorot']} אגורות")
        
        cursor.close()
        connection.close()
        print("✅ בדיקה הושלמה!")
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_interactions_table() 