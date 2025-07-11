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
    
    # וידוא שהטבלה קיימת ויצירתה אם לא
    print("🔧 מוודא שטבלת chat_messages קיימת...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT,
            user_msg TEXT,
            bot_msg TEXT,
            timestamp TIMESTAMP,
            message_type VARCHAR(100),
            telegram_message_id BIGINT,
            source_file VARCHAR(200),
            source_line_number INTEGER,
            gpt_type VARCHAR(50),
            gpt_model VARCHAR(100),
            gpt_cost_usd DECIMAL(10,6),
            gpt_tokens_input INTEGER,
            gpt_tokens_output INTEGER,
            gpt_request TEXT,
            gpt_response TEXT,
            user_data TEXT,
            bot_data TEXT,
            metadata TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # שחזור כל ההודעות
    restored_count = 0
    error_count = 0
    
    print("🚀 מתחיל שחזור מלא...")
    
    for i, msg in enumerate(backup_data):
        try:
            # הכנסת ההודעה
            cur.execute("""
                INSERT INTO chat_messages (
                    chat_id, user_msg, bot_msg, timestamp, message_type,
                    telegram_message_id, source_file, source_line_number,
                    gpt_type, gpt_model, gpt_cost_usd, gpt_tokens_input, gpt_tokens_output,
                    gpt_request, gpt_response, user_data, bot_data, metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                msg.get('chat_id'),
                msg.get('user_msg'),
                msg.get('bot_msg'),
                msg.get('timestamp'),
                msg.get('message_type', 'restored_full'),
                msg.get('telegram_message_id'),
                msg.get('source_file', 'full_backup_restore'),
                msg.get('source_line_number'),
                msg.get('gpt_type'),
                msg.get('gpt_model'),
                msg.get('gpt_cost_usd'),
                msg.get('gpt_tokens_input'),
                msg.get('gpt_tokens_output'),
                msg.get('gpt_request'),
                msg.get('gpt_response'),
                msg.get('user_data'),
                msg.get('bot_data'),
                msg.get('metadata')
            ))
            
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