#!/usr/bin/env python3
"""
תיקון נתונים קיימים במסד הנתונים - הסרת טיימסטאפ מתוכן ההודעות והסרת כפילויות
"""

import re
import sys
sys.path.append('.')

import psycopg2
from config import get_config

# קבלת ה-DB_URL
config = get_config()
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def clean_timestamp_from_text(text):
    """הסרת טיימסטאפ מתחילת הטקסט"""
    if not text:
        return text
    
    # פטרן לטיימסטאפ: [יום/חודש שעה:דקה]
    pattern = r'^\[(\d{1,2})\/(\d{1,2})\s+(\d{1,2}):(\d{1,2})\]\s*'
    
    # הסרת הטיימסטאפ מתחילת הטקסט
    cleaned_text = re.sub(pattern, '', text)
    
    return cleaned_text.strip()

def remove_duplicate_messages():
    """הסרת הודעות כפולות במסד הנתונים"""
    print("\n🔍 בודק הודעות כפולות...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # מציאת כפילויות - הודעות זהות באותו chat_id עם הפרש זמן קטן
        cur.execute("""
            WITH duplicates AS (
                SELECT 
                    id,
                    chat_id,
                    user_msg,
                    bot_msg,
                    timestamp,
                    ROW_NUMBER() OVER (
                        PARTITION BY chat_id, COALESCE(user_msg, ''), COALESCE(bot_msg, '') 
                        ORDER BY timestamp DESC
                    ) as rn
                FROM chat_messages
                WHERE chat_id IS NOT NULL
            )
            SELECT id, chat_id, user_msg, bot_msg, timestamp
            FROM duplicates 
            WHERE rn > 1
            ORDER BY timestamp DESC
            LIMIT 50
        """)
        
        duplicates = cur.fetchall()
        print(f"📋 נמצאו {len(duplicates)} הודעות כפולות")
        
        if duplicates:
            print("\n🔍 דוגמאות הודעות כפולות:")
            for i, (msg_id, chat_id, user_msg, bot_msg, timestamp) in enumerate(duplicates[:5]):
                print(f"📅 כפילות {i+1} (ID: {msg_id}, Chat: {chat_id}, Time: {timestamp})")
                print(f"   👤 User: {user_msg[:50] if user_msg else 'None'}...")
                print(f"   🤖 Bot: {bot_msg[:50] if bot_msg else 'None'}...")
            
            response = input(f"\n❓ האם להסיר {len(duplicates)} הודעות כפולות? (yes/no): ")
            if response.lower() == 'yes':
                # הסרת הכפילויות
                print(f"🗑️ מסיר {len(duplicates)} הודעות כפולות...")
                
                for msg_id, chat_id, user_msg, bot_msg, timestamp in duplicates:
                    cur.execute("DELETE FROM chat_messages WHERE id = %s", (msg_id,))
                
                conn.commit()
                print(f"✅ הוסרו {len(duplicates)} הודעות כפולות!")
            else:
                print("❌ הסרת כפילויות בוטלה")
        else:
            print("✅ אין הודעות כפולות!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה בהסרת כפילויות: {e}")
        return False
    
    return True

def clean_timestamps():
    """הסרת טיימסטאפ מתוכן ההודעות"""
    print("\n🔧 מתחיל תיקון טיימסטאפ...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקת כמות הודעות עם טיימסטאפ
        print("🔍 בודק הודעות עם טיימסטאפ...")
        
        cur.execute("""
            SELECT id, chat_id, user_msg, bot_msg 
            FROM chat_messages 
            WHERE (user_msg ~ '^\\[[0-9]{1,2}/[0-9]{1,2}\\s+[0-9]{1,2}:[0-9]{1,2}\\]') 
               OR (bot_msg ~ '^\\[[0-9]{1,2}/[0-9]{1,2}\\s+[0-9]{1,2}:[0-9]{1,2}\\]')
            ORDER BY timestamp DESC
            LIMIT 100
        """)
        
        messages_with_timestamp = cur.fetchall()
        print(f"📋 נמצאו {len(messages_with_timestamp)} הודעות עם טיימסטאפ")
        
        if not messages_with_timestamp:
            print("✅ אין הודעות עם טיימסטאפ לתיקון!")
            return True
        
        # הצגת דוגמאות
        print("\n🔍 דוגמאות הודעות שיתוקנו:")
        for i, (msg_id, chat_id, user_msg, bot_msg) in enumerate(messages_with_timestamp[:5]):
            print(f"\n📅 הודעה {i+1} (ID: {msg_id}, Chat: {chat_id}):")
            
            if user_msg and user_msg.startswith('['):
                cleaned_user = clean_timestamp_from_text(user_msg)
                print(f"👤 User: '{user_msg[:50]}...' -> '{cleaned_user[:50]}...'")
            
            if bot_msg and bot_msg.startswith('['):
                cleaned_bot = clean_timestamp_from_text(bot_msg)
                print(f"🤖 Bot: '{bot_msg[:50]}...' -> '{cleaned_bot[:50]}...'")
        
        # שאלת אישור
        response = input(f"\n❓ האם לתקן {len(messages_with_timestamp)} הודעות? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ תיקון בוטל")
            return False
        
        # תיקון ההודעות
        print(f"\n🔧 מתקן {len(messages_with_timestamp)} הודעות...")
        
        updated_count = 0
        for msg_id, chat_id, user_msg, bot_msg in messages_with_timestamp:
            
            cleaned_user_msg = clean_timestamp_from_text(user_msg) if user_msg else user_msg
            cleaned_bot_msg = clean_timestamp_from_text(bot_msg) if bot_msg else bot_msg
            
            # עדכון רק אם השתנה משהו
            if (cleaned_user_msg != user_msg) or (cleaned_bot_msg != bot_msg):
                cur.execute("""
                    UPDATE chat_messages 
                    SET user_msg = %s, bot_msg = %s 
                    WHERE id = %s
                """, (cleaned_user_msg, cleaned_bot_msg, msg_id))
                
                updated_count += 1
                
                if updated_count % 10 == 0:
                    print(f"✅ עודכנו {updated_count} הודעות...")
        
        # שמירת שינויים
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n🎉 תיקון הושלם בהצלחה! עודכנו {updated_count} הודעות")
        
    except Exception as e:
        print(f"❌ שגיאה בתיקון: {e}")
        return False
    
    return True

def main():
    print("🔧 מתחיל תיקון מקיף של מסד הנתונים...")
    print("=" * 60)
    
    # שלב 1: הסרת כפילויות
    if not remove_duplicate_messages():
        print("❌ נכשל בהסרת כפילויות")
        return
    
    # שלב 2: הסרת טיימסטאפ
    if not clean_timestamps():
        print("❌ נכשל בתיקון טיימסטאפ")
        return
    
    print("\n" + "=" * 60)
    print("🎉 תיקון מקיף הושלם בהצלחה!")
    print("✅ הודעות כפולות הוסרו")
    print("✅ טיימסטאפ הוסר מתוכן ההודעות")

if __name__ == "__main__":
    main() 