#!/usr/bin/env python3
"""
📋 הצגת כל המשתמשים שיש להם CHAT_ID
"""

import psycopg2
from datetime import datetime
from config import config
from utils import safe_str

def get_users_with_chat_id():
    """מציג את כל המשתמשים שיש להם chat_id (לא NULL)"""
    
    try:
        # חיבור למסד הנתונים
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        print("👥 === רשימת משתמשים עם CHAT_ID ===")
        print()
        
        # בדיקת מבנה הטבלה
        print("🔍 בודק מבנה טבלת user_profiles...")
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_profiles' 
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        print("📊 עמודות זמינות:")
        for col_name, col_type in columns:
            print(f"   - {col_name} ({col_type})")
        print()
        
        # שליפת כל המשתמשים עם chat_id (רק העמודות שקיימות)
        cur.execute("""
            SELECT 
                chat_id,
                approved,
                code_approve,
                updated_at,
                name,
                age,
                pronoun_preference,
                occupation_or_role,
                attracted_to,
                relationship_type
            FROM user_profiles 
            WHERE chat_id IS NOT NULL 
            ORDER BY updated_at DESC
        """)
        
        users = cur.fetchall()
        
        if not users:
            print("❌ לא נמצאו משתמשים עם chat_id")
            return
        
        print(f"📊 נמצאו {len(users)} משתמשים עם chat_id:")
        print("=" * 100)
        
        for i, (chat_id, approved, code_approve, updated_at, name, age, pronoun_preference, occupation_or_role, attracted_to, relationship_type) in enumerate(users, 1):
            safe_chat_id = safe_str(chat_id)
            status_emoji = "✅" if approved else "⏳"
            status_text = "מאושר" if approved else "ממתין לאישור"
            
            print(f"{i:2d}. {status_emoji} {safe_chat_id}")
            print(f"    👤 שם: {name if name else 'ללא שם'}")
            print(f"    🎂 גיל: {age if age else 'לא צוין'}")
            print(f"    🗣️ כינוי: {pronoun_preference if pronoun_preference else 'לא צוין'}")
            print(f"    💼 תפקיד: {occupation_or_role if occupation_or_role else 'לא צוין'}")
            print(f"    💕 נמשך ל: {attracted_to if attracted_to else 'לא צוין'}")
            print(f"    👥 סוג קשר: {relationship_type if relationship_type else 'לא צוין'}")
            print(f"    🔑 קוד: {code_approve if code_approve else 'ללא קוד'}")
            print(f"    🔄 עדכון אחרון: {updated_at.strftime('%d/%m/%Y %H:%M') if updated_at else 'לא ידוע'}")
            print(f"    📊 סטטוס: {status_text}")
            print()
        
        # סיכום
        approved_count = sum(1 for user in users if user[1])  # approved
        pending_count = len(users) - approved_count
        
        print("📈 === סיכום ===")
        print(f"✅ מאושרים: {approved_count}")
        print(f"⏳ ממתינים: {pending_count}")
        print(f"📊 סך הכל: {len(users)}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")

if __name__ == "__main__":
    get_users_with_chat_id() 