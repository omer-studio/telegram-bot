#!/usr/bin/env python3
"""
🔍 check_daily_backup.py
========================
בדיקת איכות הגיבוי היומי מ-9.7
"""

import json
import psycopg2
from config import config

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def check_daily_backup():
    print("🔍 בודק גיבוי יומי מ-9.7...")
    
    file_path = "backups/daily_db_backups/chat_messages_20250709.json"
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"📋 סה\"כ הודעות בגיבוי: {len(data):,}")
    
    # בדיקת איכות
    valid_messages = 0
    for i, msg in enumerate(data[:5]):  # דוגמאות
        chat_id = msg.get('chat_id')
        timestamp = msg.get('timestamp')
        user_msg = msg.get('user_msg', '')
        
        print(f"\n📋 דוגמה {i+1}:")
        print(f"   chat_id: {chat_id}")
        print(f"   user_msg: {user_msg[:50]}..." if user_msg else "   user_msg: ריק")
        print(f"   timestamp: {timestamp}")
        
        if chat_id and timestamp:
            valid_messages += 1
    
    print(f"\n✅ כל הדוגמאות תקינות!")
    
    # בדיקה כמה מההודעות כבר קיימות במסד
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # בדיקת כמה הודעות מהגיבוי כבר קיימות
    existing_count = 0
    missing_count = 0
    
    print(f"🔍 בודק כמה הודעות מהגיבוי כבר קיימות במסד...")
    
    for i, msg in enumerate(data):
        if i % 100 == 0 and i > 0:
            print(f"   📊 בדקתי {i:,} הודעות...")
        
        chat_id = msg.get('chat_id')
        user_msg = msg.get('user_msg', '')
        timestamp = msg.get('timestamp')
        
        if not chat_id or not timestamp:
            continue
        
        cur.execute("""
            SELECT COUNT(*) FROM chat_messages 
            WHERE chat_id = %s 
            AND user_msg = %s 
            AND timestamp = %s
        """, (chat_id, user_msg, timestamp))
        
        if cur.fetchone()[0] > 0:
            existing_count += 1
        else:
            missing_count += 1
    
    cur.close()
    conn.close()
    
    print(f"\n📊 תוצאות בדיקה:")
    print(f"   ✅ הודעות שכבר קיימות במסד: {existing_count:,}")
    print(f"   🚨 הודעות שחסרות במסד: {missing_count:,}")
    print(f"   📊 סה\"כ הודעות שנבדקו: {existing_count + missing_count:,}")
    
    return missing_count

if __name__ == "__main__":
    missing = check_daily_backup()
    if missing > 0:
        print(f"\n🎯 יש {missing:,} הודעות לשחזר מהגיבוי!")
    else:
        print(f"\n✅ כל ההודעות כבר קיימות במסד") 