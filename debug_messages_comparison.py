#!/usr/bin/env python3
"""
🔍 debug_messages_comparison.py
===============================
בדיקה מדוע כל ההודעות נדחות
"""

import psycopg2
import json
from datetime import datetime
from config import config

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def debug_comparison():
    print("🔍 בודק מדוע כל ההודעות נדחות...")
    
    # טעינת הקובץ
    file_path = "extracted_chat_data_20250706_155957.json"
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    file_messages = data['chat_messages']
    print(f"📋 הודעות בקובץ: {len(file_messages):,}")
    
    # חיבור למסד הנתונים
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # בדיקת מספר הודעות במסד
    cur.execute("SELECT COUNT(*) FROM chat_messages")
    db_count = cur.fetchone()[0]
    print(f"📊 הודעות במסד: {db_count:,}")
    
    # דוגמה מהקובץ
    sample_msg = file_messages[0]
    print(f"\n🔍 דוגמת הודעה מהקובץ:")
    print(f"   chat_id: {sample_msg.get('chat_id')}")
    print(f"   user_msg: {sample_msg.get('user_msg', '')[:50]}...")
    print(f"   timestamp: {sample_msg.get('timestamp')}")
    
    # בדיקה האם ההודעה הזו קיימת במסד
    cur.execute("""
        SELECT COUNT(*) FROM chat_messages 
        WHERE chat_id = %s 
        AND user_msg = %s 
        AND timestamp = %s
    """, (sample_msg.get('chat_id'), sample_msg.get('user_msg', ''), sample_msg.get('timestamp')))
    
    exists = cur.fetchone()[0]
    print(f"   קיימת במסד: {'כן' if exists > 0 else 'לא'}")
    
    if exists > 0:
        print("✅ ההודעה כבר קיימת - זו הסיבה שהיא נדחית")
        
        # בואו נבדוק אם יש הודעות במסד שלא בקובץ
        print(f"\n🔍 בודק אם יש הודעות במסד שלא בקובץ...")
        
        # בדיקת טווח תאריכים
        cur.execute("""
            SELECT 
                MIN(timestamp) as oldest,
                MAX(timestamp) as newest,
                COUNT(*) as total
            FROM chat_messages
        """)
        db_range = cur.fetchone()
        print(f"📅 טווח תאריכים במסד: {db_range[0]} עד {db_range[1]} ({db_range[2]} הודעות)")
        
        # בדיקת טווח תאריכים בקובץ
        timestamps = [msg.get('timestamp') for msg in file_messages if msg.get('timestamp')]
        file_oldest = min(timestamps) if timestamps else None
        file_newest = max(timestamps) if timestamps else None
        print(f"📅 טווח תאריכים בקובץ: {file_oldest} עד {file_newest} ({len(file_messages)} הודעות)")
        
        # בדיקת הודעות חדשות במסד
        if file_newest:
            cur.execute("""
                SELECT COUNT(*) FROM chat_messages 
                WHERE timestamp > %s
            """, (file_newest,))
            newer_messages = cur.fetchone()[0]
            print(f"📊 הודעות במסד שחדשות מהקובץ: {newer_messages:,}")
            
            if newer_messages > 0:
                print("💡 זה מסביר מדוע במסד יש פחות הודעות - הן חדשות יותר!")
    
    else:
        print("❓ ההודעה לא קיימת - זה מוזר...")
        
        # בואו נבדוק הודעות דומות
        cur.execute("""
            SELECT chat_id, user_msg, timestamp 
            FROM chat_messages 
            WHERE chat_id = %s
            LIMIT 3
        """, (sample_msg.get('chat_id'),))
        
        similar_msgs = cur.fetchall()
        print(f"🔍 הודעות דומות במסד:")
        for msg in similar_msgs:
            print(f"   chat_id: {msg[0]}, user_msg: {msg[1][:30]}..., timestamp: {msg[2]}")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    debug_comparison() 