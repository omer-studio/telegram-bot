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
    from simple_data_manager import DataManager
    from utils import safe_str, get_logger
    
    logger = get_logger(__name__)
    
    def check_code_15689309():
        """
        בדיקה ישירה של קוד 15689309
        """
        try:
            data_manager = DataManager()
            
            logger.info("בדיקת קוד אפרובל 15689309")
            print("🔍 בדיקת קוד אפרובל 15689309")
            print("=" * 50)
            
            # בדיקה ישירה של הקוד
            query = """
                SELECT 
                    chat_id, 
                    code_approve, 
                    code_try, 
                    approved, 
                    updated_at,
                    name
                FROM user_profiles 
                WHERE code_approve = '15689309'
            """
            results = data_manager.execute_query(query)
            
            if not results:
                print("❌ קוד 15689309 לא נמצא במסד הנתונים!")
                
                # חיפוש קודים דומים
                similar_query = """
                    SELECT code_approve, chat_id, approved 
                    FROM user_profiles 
                    WHERE code_approve LIKE '%15689309%'
                       OR code_approve LIKE '%15689%'
                       OR code_approve LIKE '%9309%'
                    LIMIT 5
                """
                similar = data_manager.execute_query(similar_query)
                
                if similar:
                    print("\n🔍 קודים דומים:")
                    for code, chat_id, approved in similar:
                        safe_chat_id = safe_str(chat_id)
                        print(f"   {code} -> chat_id={safe_chat_id}, approved={approved}")
                
            else:
                print(f"✅ נמצא קוד 15689309!")
                for chat_id, code, code_try, approved, updated_at, name in results:
                    safe_chat_id = safe_str(chat_id)
                    print(f"\n📋 תוצאה:")
                    print(f"   📱 chat_id: {safe_chat_id}")
                    print(f"   🔐 code_approve: {code}")
                    print(f"   🔢 code_try: {code_try}")
                    print(f"   ✅ approved: {approved}")
                    print(f"   🕐 updated_at: {updated_at}")
                    print(f"   👤 name: {name}")
                    
                    # ניתוח המצב
                    if chat_id and str(chat_id).strip():
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
            
        except Exception as e:
            logger.error(f"שגיאה בבדיקת קוד: {e}")
            print(f"❌ שגיאה: {e}")
            import traceback
            traceback.print_exc()
    
    def check_recent_users():
        """
        בדיקת משתמשים שהתחברו לאחרונה
        """
        try:
            data_manager = DataManager()
            
            logger.info("בדיקת משתמשים אחרונים")
            print(f"\n🔍 משתמשים שהתחברו לאחרונה:")
            print("=" * 60)
            
            query = """
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
            """
            results = data_manager.execute_query(query)
            
            if results:
                for code_approve, chat_id, approved, code_try, updated_at in results:
                    safe_chat_id = safe_str(chat_id)
                    status = "✅ מאושר" if approved else "⏳ ממתין לאישור"
                    print(f"   {code_approve} -> {safe_chat_id} | {status} | {updated_at}")
            else:
                print("   אין משתמשים במסד")
            
        except Exception as e:
            logger.error(f"שגיאה בבדיקת משתמשים: {e}")
            print(f"❌ שגיאה: {e}")

    if __name__ == "__main__":
        check_code_15689309()
        check_recent_users()

except ImportError as e:
    print(f"❌ שגיאה בייבוא: {e}")
    print("נסה להריץ מתיקייה שבה יש את הקבצים של הבוט") 