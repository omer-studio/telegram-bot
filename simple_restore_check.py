#!/usr/bin/env python3
"""
🔍 simple_restore_check.py
==========================
בדיקה פשוטה של קבצי הגיבוי לפני שחזור
"""

import json
import os
from datetime import datetime

def check_backup_file(file_path, name):
    """בודק קובץ גיבוי בודד"""
    print(f"\n🔍 בודק {name}: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ קובץ לא קיים")
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📊 סוג נתונים: {type(data)}")
        
        if isinstance(data, list):
            print(f"📋 מספר פריטים: {len(data)}")
            if data:
                print(f"🔍 דוגמת פריט ראשון:")
                first_item = data[0]
                if isinstance(first_item, dict):
                    print(f"   שדות: {list(first_item.keys())}")
                    if 'chat_id' in first_item:
                        print(f"   chat_id: {first_item.get('chat_id')}")
                    if 'user_msg' in first_item:
                        user_msg = first_item.get('user_msg', '')
                        print(f"   user_msg: {user_msg[:50]}..." if len(user_msg) > 50 else f"   user_msg: {user_msg}")
                    if 'timestamp' in first_item:
                        print(f"   timestamp: {first_item.get('timestamp')}")
        
        elif isinstance(data, dict):
            print(f"📋 מפתחות: {list(data.keys())}")
            for key, value in data.items():
                if isinstance(value, list):
                    print(f"   {key}: {len(value)} פריטים")
                else:
                    print(f"   {key}: {type(value)}")
        
        return data
        
    except Exception as e:
        print(f"❌ שגיאה בקריאת קובץ: {e}")
        return None

def main():
    print("🔍 === בדיקת קבצי גיבוי ===")
    print(f"🕐 זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print()
    
    # רשימת קבצים לבדיקה
    files_to_check = [
        ("backups/daily_db_backups/chat_messages_20250709.json", "גיבוי יומי 9.7"),
        ("backups/data_backup_20250706_141212/chat_history.json", "גיבוי ישן 6.7"),
        ("extracted_chat_data_20250706_155957.json", "נתונים מחולצים 6.7"),
        ("backups/data_backup_20250706_141212/chat_history.json.bak", "גיבוי bak 6.7")
    ]
    
    results = {}
    
    for file_path, name in files_to_check:
        data = check_backup_file(file_path, name)
        if data is not None:
            results[name] = data
    
    print(f"\n📊 === סיכום ===")
    total_messages = 0
    for name, data in results.items():
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict) and 'chat_messages' in data:
            count = len(data['chat_messages'])
        else:
            count = 0
        
        print(f"   {name}: {count:,} הודעות")
        total_messages += count
    
    print(f"\n🎯 סה\"כ הודעות זמינות לשחזור: {total_messages:,}")
    
    # הודעות נוכחיות במסד
    try:
        import psycopg2
        from config import config
        
        conn = psycopg2.connect(config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM chat_messages")
        current_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        
        print(f"📊 הודעות נוכחיות במסד: {current_count:,}")
        print(f"🚨 פוטנציאל לשחזור: {total_messages - current_count:,} הודעות")
        
    except Exception as e:
        print(f"⚠️ לא ניתן לבדוק מסד נתונים: {e}")

if __name__ == "__main__":
    main() 