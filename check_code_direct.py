#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔍 בדיקה ישירה של קוד אפרובל 15689309
"""

import json
import psycopg2

def load_config():
    """טעינת קונפיגורציה"""
    try:
        with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return {}

def check_code_15689309():
    """
    בדיקה ישירה של קוד 15689309
    """
    try:
        config = load_config()
        if not config:
            return
            
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        if not db_url:
            print("❌ לא נמצא URL למסד הנתונים")
            return
            
        print("🔍 בדיקת קוד אפרובל 15689309")
        print("=" * 50)
        
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # בדיקה ישירה של הקוד
        cur.execute("""
            SELECT 
                chat_id, 
                code_approve, 
                code_try, 
                approved, 
                updated_at,
                name
            FROM user_profiles 
            WHERE code_approve = '15689309'
        """)
        
        results = cur.fetchall()
        
        if not results:
            print("❌ קוד 15689309 לא נמצא במסד הנתונים!")
            
            # חיפוש קודים דומים
            print("\n🔍 מחפש קודים דומים...")
            cur.execute("""
                SELECT code_approve, chat_id, approved 
                FROM user_profiles 
                WHERE code_approve LIKE '%156893%'
                   OR code_approve LIKE '%15689%'
                   OR code_approve LIKE '%89309%'
                LIMIT 10
            """)
            
            similar = cur.fetchall()
            if similar:
                print("📋 קודים דומים שנמצאו:")
                for code, chat_id, approved in similar:
                    status = "✅ מאושר" if approved else "⏳ ממתין"
                    print(f"   {code} -> chat_id={chat_id} | {status}")
            else:
                print("❌ לא נמצאו קודים דומים")
                
        else:
            print(f"✅ נמצא קוד 15689309!")
            for chat_id, code, code_try, approved, updated_at, name in results:
                print(f"\n📋 פרטי המשתמש:")
                print(f"   📱 chat_id: {chat_id}")
                print(f"   🔐 code_approve: {code}")
                print(f"   🔢 code_try: {code_try}")
                print(f"   ✅ approved: {approved}")
                print(f"   🕐 updated_at: {updated_at}")
                print(f"   👤 name: {name}")
                
                # ניתוח המצב
                if chat_id and chat_id.strip():
                    if approved:
                        print("\n🎯 המצב: המשתמש מאושר לחלוטין!")
                        print("🤖 הבוט אמור: לתת גישה מלאה")
                        print("🚨 בעיה: למה הבוט מבקש סיסמה?!")
                    else:
                        print("\n🎯 המצב: המשתמש נתן קוד נכון אבל לא אישר תנאים")
                        print("🤖 הבוט אמור: לשלוח הודעת תנאים")
                        print("❌ הבוט לא אמור לבקש סיסמה!")
                else:
                    print("\n🎯 המצב: קוד קיים אבל לא משויך למשתמש")
                    print("🤖 הבוט אמור: לבקש מהמשתמש להזין את הקוד")
        
        # בדיקת משתמשים אחרונים
        print(f"\n🔍 5 משתמשים אחרונים:")
        print("=" * 50)
        
        cur.execute("""
            SELECT 
                code_approve, 
                chat_id, 
                approved, 
                code_try,
                updated_at,
                name
            FROM user_profiles 
            WHERE chat_id IS NOT NULL 
            AND code_approve IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 5
        """)
        
        recent = cur.fetchall()
        
        if recent:
            for code_approve, chat_id, approved, code_try, updated_at, name in recent:
                status = "✅ מאושר" if approved else "⏳ ממתין"
                print(f"   {code_approve} -> {chat_id} | {status} | {name}")
        else:
            print("   אין משתמשים במסד")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_code_15689309() 