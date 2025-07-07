#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🔍 בדיקה פשוטה של קוד אפרובל 15689309
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to use existing database functions
try:
    from db_manager import DB_URL
    import psycopg2
    
    def check_code_15689309():
        """
        בדיקה ישירה של קוד 15689309
        """
        try:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            
            print("🔍 בדיקת קוד אפרובל 15689309")
            print("=" * 50)
            
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
                cur.execute("""
                    SELECT code_approve, chat_id, approved 
                    FROM user_profiles 
                    WHERE code_approve LIKE '%15689309%'
                       OR code_approve LIKE '%15689%'
                       OR code_approve LIKE '%9309%'
                    LIMIT 5
                """)
                
                similar = cur.fetchall()
                if similar:
                    print("\n🔍 קודים דומים:")
                    for code, chat_id, approved in similar:
                        print(f"   {code} -> chat_id={chat_id}, approved={approved}")
                
            else:
                print(f"✅ נמצא קוד 15689309!")
                for chat_id, code, code_try, approved, updated_at, name in results:
                    print(f"\n📋 תוצאה:")
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
                            print("🤖 הבוט אמור: לתת גישה מלאה - אין סיבה לבקש סיסמה!")
                            print("🚨 זו הבעיה - המשתמש מאושר אבל הבוט מבקש סיסמה!")
                        else:
                            print("\n🎯 המצב: המשתמש נתן קוד נכון אבל לא אישר תנאים")
                            print("🤖 הבוט אמור: לשלוח הודעת תנאים ולבקש אישור")
                            print("❌ הבוט לא אמור לבקש סיסמה/קוד שוב!")
                    else:
                        print("\n🎯 המצב: קוד קיים אבל לא משויך למשתמש")
                        print("🤖 הבוט אמור: לבקש מהמשתמש להזין את הקוד")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ שגיאה: {e}")
            import traceback
            traceback.print_exc()
    
    def check_recent_users():
        """
        בדיקת משתמשים שהתחברו לאחרונה
        """
        try:
            conn = psycopg2.connect(DB_URL)
            cur = conn.cursor()
            
            print(f"\n🔍 משתמשים שהתחברו לאחרונה:")
            print("=" * 60)
            
            cur.execute("""
                SELECT 
                    code_approve, 
                    chat_id, 
                    approved, 
                    code_try,
                    updated_at
                FROM user_profiles 
                WHERE chat_id IS NOT NULL 
                AND code_approve IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 5
            """)
            
            results = cur.fetchall()
            
            if results:
                for code_approve, chat_id, approved, code_try, updated_at in results:
                    status = "✅ מאושר" if approved else "⏳ ממתין לאישור"
                    print(f"   {code_approve} -> {chat_id} | {status} | {updated_at}")
            else:
                print("   אין משתמשים במסד")
            
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"❌ שגיאה: {e}")

    if __name__ == "__main__":
        check_code_15689309()
        check_recent_users()

except ImportError as e:
    print(f"❌ שגיאה בייבוא: {e}")
    print("נסה להריץ מתיקייה שבה יש את הקבצים של הבוט") 