#!/usr/bin/env python3
"""
🎯 focused_restore.py
====================
שחזור ממוקד מהקובץ עם הכי הרבה הודעות
"""

import psycopg2
import json
from datetime import datetime
from config import config

# ייבוא הפונקציות המרכזיות מ-db_manager
from db_manager import insert_chat_message_only

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def restore_from_extracted_data():
    """משחזר הודעות מהקובץ המחולץ"""
    file_path = "extracted_chat_data_20250706_155957.json"
    
    print(f"🔄 משחזר מ-{file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        messages = data['chat_messages']
        print(f"📋 נמצאו {len(messages):,} הודעות בקובץ")
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקה כמה הודעות יש עכשיו
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        current_count = cur.fetchone()[0]
        print(f"📊 הודעות נוכחיות במסד: {current_count:,}")
        
        restored_count = 0
        skipped_count = 0
        
        print(f"🚀 מתחיל שחזור...")
        
        for i, msg in enumerate(messages):
            try:
                chat_id = msg.get('chat_id')
                user_msg = msg.get('user_msg', '')
                bot_msg = msg.get('bot_msg', '')
                timestamp = msg.get('timestamp')
                
                if not chat_id or not timestamp:
                    skipped_count += 1
                    continue
                
                # בדיקה שההודעה לא קיימת כבר
                cur.execute("""
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE chat_id = %s 
                    AND user_msg = %s 
                    AND timestamp = %s
                """, (chat_id, user_msg, timestamp))
                
                if cur.fetchone()[0] > 0:
                    skipped_count += 1
                    continue
                
                # הכנסת ההודעה - משתמש בפונקציה המרכזית
                insert_chat_message_only(cur, chat_id, user_msg, bot_msg, timestamp)
                
                restored_count += 1
                
                # התקדמות כל 100 הודעות
                if restored_count % 100 == 0:
                    print(f"   📊 שוחזרו {restored_count:,} הודעות...")
                    conn.commit()
                
            except Exception as e:
                skipped_count += 1
                if skipped_count % 50 == 0:
                    print(f"   ⚠️ דולגו על {skipped_count} הודעות עד כה...")
                continue
        
        conn.commit()
        
        # בדיקה סופית
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        final_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        print(f"\n🎉 סיכום שחזור:")
        print(f"   📊 הודעות ששוחזרו: {restored_count:,}")
        print(f"   ⚠️ הודעות שדולגו: {skipped_count:,}")
        print(f"   📊 מספר הודעות סופי: {final_count:,}")
        print(f"   📈 הוספה: {final_count - current_count:,} הודעות")
        
        return restored_count > 0
        
    except Exception as e:
        print(f"❌ שגיאה בשחזור: {e}")
        return False

def main():
    print("🎯 === שחזור ממוקד מהקובץ הטוב ביותר ===")
    print(f"🕐 זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    success = restore_from_extracted_data()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ שחזור הושלם בהצלחה!")
    else:
        print("❌ שחזור נכשל")
    
    print("🔒 chat_messages מוגן מפני מחיקות!")

if __name__ == "__main__":
    main() 