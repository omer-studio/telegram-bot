#!/usr/bin/env python3
"""
🔍 analyze_extracted_data.py
============================
ניתוח איכות הנתונים המחולצים
"""

import json
from collections import Counter

def analyze_data_quality():
    print("🔍 מנתח איכות הנתונים המחולצים...")
    
    file_path = "extracted_chat_data_20250706_155957.json"
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    messages = data['chat_messages']
    print(f"📋 סה\"כ הודעות בקובץ: {len(messages):,}")
    
    # ספירת הודעות תקינות
    valid_messages = 0
    invalid_messages = 0
    chat_id_missing = 0
    timestamp_missing = 0
    user_msg_empty = 0
    
    chat_ids = set()
    
    for i, msg in enumerate(messages):
        chat_id = msg.get('chat_id')
        timestamp = msg.get('timestamp')
        user_msg = msg.get('user_msg', '')
        
        if not chat_id:
            chat_id_missing += 1
        if not timestamp:
            timestamp_missing += 1
        if not user_msg or user_msg.strip() == '':
            user_msg_empty += 1
        
        if chat_id and timestamp:
            valid_messages += 1
            chat_ids.add(chat_id)
        else:
            invalid_messages += 1
            
        # הצגת כמה דוגמאות
        if i < 5:
            print(f"\n📋 הודעה {i+1}:")
            print(f"   chat_id: {chat_id}")
            print(f"   user_msg: {user_msg[:50]}..." if user_msg else "   user_msg: ריק")
            print(f"   timestamp: {timestamp}")
            print(f"   תקינה: {'כן' if chat_id and timestamp else 'לא'}")
    
    print(f"\n📊 סיכום איכות נתונים:")
    print(f"   ✅ הודעות תקינות: {valid_messages:,}")
    print(f"   ❌ הודעות לא תקינות: {invalid_messages:,}")
    print(f"   👥 משתמשים ייחודיים: {len(chat_ids):,}")
    print(f"   🚫 חסרי chat_id: {chat_id_missing:,}")
    print(f"   🚫 חסרי timestamp: {timestamp_missing:,}")
    print(f"   📝 הודעות ריקות: {user_msg_empty:,}")
    
    # בדיקת התפלגות לפי משתמשים
    if valid_messages > 0:
        print(f"\n👥 מדגם משתמשים:")
        chat_id_counter = Counter()
        for msg in messages:
            if msg.get('chat_id'):
                chat_id_counter[msg.get('chat_id')] += 1
        
        top_users = chat_id_counter.most_common(5)
        for chat_id, count in top_users:
            print(f"   {chat_id}: {count} הודעות")
    
    return valid_messages

if __name__ == "__main__":
    valid_count = analyze_data_quality()
    print(f"\n🎯 הודעות ראויות לשחזור: {valid_count:,}") 