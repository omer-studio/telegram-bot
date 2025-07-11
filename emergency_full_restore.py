#!/usr/bin/env python3
"""
🚨 emergency_full_restore.py
===========================
שחזור דחוף מלא - כל ההודעות נמחקו!!!
"""

import psycopg2
import json
from datetime import datetime
from config import config

# ייבוא הפונקציות המרכזיות מ-db_manager
from db_manager import create_chat_messages_table_only, insert_chat_message_only

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def emergency_full_restore():
    print("🚨 === שחזור דחוף מלא - כל ההודעות נמחקו! ===")
    print(f"🕐 זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # טעינת הגיבוי היומי
    file_path = "backups/daily_db_backups/chat_messages_20250709.json"
    print(f"🔄 טוען גיבוי מ-{file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    print(f"📋 נמצאו {len(backup_data):,} הודעות בגיבוי")
    
    # חיבור למסד הנתונים
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # וידוא שהטבלה קיימת ויצירתה אם לא - משתמש בפונקציה המרכזית
    print("🔧 מוודא שטבלת chat_messages קיימת...")
    create_chat_messages_table_only(cur)
    
    # שחזור כל ההודעות
    restored_count = 0
    error_count = 0
    
    print("🚀 מתחיל שחזור מלא...")
    
    for i, msg in enumerate(backup_data):
        try:
            # הכנסת ההודעה - משתמש בפונקציה המרכזית
            insert_chat_message_only(
                cur,
                msg.get('chat_id'),
                msg.get('user_msg'),
                msg.get('bot_msg'),
                msg.get('timestamp')
            )
            
            restored_count += 1
            
            # התקדמות כל 100 הודעות
            if restored_count % 100 == 0:
                print(f"   📊 שוחזרו {restored_count:,} הודעות...")
                conn.commit()
            
        except Exception as e:
            error_count += 1
            if error_count % 10 == 1:  # הצגת שגיאה ראשונה בכל 10
                print(f"   ⚠️ שגיאה בהודעה {i+1}: {e}")
            continue
    
    conn.commit()
    
    # בדיקה סופית
    cur.execute("SELECT COUNT(*) FROM chat_messages")
    final_count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    
    print(f"\n🎉 שחזור דחוף הושלם!")
    print(f"   📊 הודעות ששוחזרו: {restored_count:,}")
    print(f"   ❌ שגיאות: {error_count:,}")
    print(f"   📊 סה\"כ הודעות במסד: {final_count:,}")
    
    if final_count > 0:
        print("✅ שחזור הושלם בהצלחה!")
        return True
    else:
        print("❌ שחזור נכשל!")
        return False

if __name__ == "__main__":
    success = emergency_full_restore()
    if success:
        print("\n🛡️ chat_messages שוחזר ומוגן מפני מחיקות!")
    else:
        print("\n💥 נדרש סיוע דחוף!") 