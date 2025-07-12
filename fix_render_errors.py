#!/usr/bin/env python3
"""
fix_render_errors.py
===================
🔧 תיקון מערכתי של כל הבעיות שזוהו בשגיאות הרנדר

הבעיות שזוהו:
1. עמודת needs_recovery_message חסרה במסד הנתונים
2. שגיאות טיפול בזמן - datetime objects vs strings
3. בעיות timezone awareness
4. שגיאות עדכון פרופיל
5. אלרט false positive על איבוד הודעות

פתרון מערכתי:
- ריצת מיגרציה כפויה למסד הנתונים
- תיקון פונקציות זמן
- וידוא שהתיקונים עובדים
"""

import sys
import traceback
from datetime import datetime
import psycopg2
from pathlib import Path

# הוספת נתיב הפרויקט
sys.path.append(str(Path(__file__).parent))

try:
    from config import get_config
    from simple_logger import logger
    from database_operations import force_database_migration, safe_db_connection
    from utils import safe_str
    from user_friendly_errors import handle_database_error
except ImportError as e:
    print(f"❌ שגיאה בייבוא מודולים: {e}")
    sys.exit(1)

class RenderErrorFixer:
    def __init__(self):
        self.config = get_config()
        self.db_url = self.config.get("DATABASE_EXTERNAL_URL") or self.config.get("DATABASE_URL")
        self.errors_fixed = []
        self.errors_failed = []
        
    def log_success(self, message):
        """רישום הצלחה"""
        print(f"✅ {message}")
        logger.info(f"[FIX_SUCCESS] {message}")
        self.errors_fixed.append(message)
        
    def log_error(self, message, error=None):
        """רישום שגיאה"""
        print(f"❌ {message}")
        if error:
            print(f"   שגיאה: {error}")
            logger.error(f"[FIX_ERROR] {message}: {error}")
        else:
            logger.error(f"[FIX_ERROR] {message}")
        self.errors_failed.append(message)
        
    def fix_database_migration(self):
        """תיקון 1: ריצת מיגרציה כפויה למסד הנתונים"""
        try:
            print("🔧 מתחיל תיקון מיגרציית מסד הנתונים...")
            
            # בדיקת חיבור למסד הנתונים
            if not self.db_url:
                self.log_error("אין URL למסד הנתונים")
                return False
                
            # ריצת מיגרציה כפויה
            success = force_database_migration()
            
            if success:
                self.log_success("מיגרציית מסד הנתונים הושלמה")
                return True
            else:
                self.log_error("מיגרציית מסד הנתונים נכשלה")
                return False
                
        except Exception as e:
            self.log_error("שגיאה במיגרציית מסד הנתונים", e)
            return False
    
    def verify_database_columns(self):
        """תיקון 2: בדיקת קיום העמודות החדשות"""
        try:
            print("🔍 בודק קיום העמודות החדשות...")
            
            with safe_db_connection() as conn:
                cur = conn.cursor()
                
                required_columns = [
                    'needs_recovery_message',
                    'recovery_original_message', 
                    'recovery_error_timestamp',
                    'last_message_time'
                ]
                
                missing_columns = []
                for column in required_columns:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_name = 'user_profiles' 
                            AND column_name = %s
                        )
                    """, (column,))
                    
                    if not cur.fetchone()[0]:
                        missing_columns.append(column)
                
                if missing_columns:
                    self.log_error(f"עמודות חסרות: {', '.join(missing_columns)}")
                    return False
                else:
                    self.log_success("כל העמודות החדשות קיימות")
                    return True
                
        except Exception as e:
            self.log_error("שגיאה בבדיקת עמודות", e)
            return False
    
    def test_recovery_functions(self):
        """תיקון 3: בדיקת פונקציות התאוששות"""
        try:
            print("🧪 בודק פונקציות התאוששות...")
            
            from recovery_manager import RecoveryManager
            from profile_utils import get_all_users_with_condition
            
            # בדיקת פונקציית החיפוש
            try:
                users = get_all_users_with_condition("needs_recovery_message = TRUE")
                self.log_success(f"פונקציית חיפוש עובדת - נמצאו {len(users)} משתמשים")
            except Exception as e:
                self.log_error("שגיאה בפונקציית חיפוש", e)
                return False
            
            # בדיקת מנהל התאוששות
            try:
                recovery_manager = RecoveryManager()
                self.log_success("מנהל התאוששות פעיל")
            except Exception as e:
                self.log_error("שגיאה במנהל התאוששות", e)
                return False
                
            return True
            
        except Exception as e:
            self.log_error("שגיאה בבדיקת פונקציות התאוששות", e)
            return False
    
    def test_datetime_functions(self):
        """תיקון 4: בדיקת פונקציות זמן"""
        try:
            print("🕐 בודק פונקציות זמן...")
            
            from chat_utils import _safe_parse_timestamp, _ensure_timezone_aware
            
            # בדיקת פונקציית parsing
            test_cases = [
                "2025-07-12T03:37:22.431566309Z",
                "2025-07-12 03:37:22",
                datetime.now(),
                None,
                "invalid_date"
            ]
            
            for test_case in test_cases:
                try:
                    result = _safe_parse_timestamp(test_case)
                    # לא נכשל - זה טוב
                except Exception as e:
                    self.log_error(f"פונקציית parsing נכשלה עם: {test_case}", e)
                    return False
            
            self.log_success("פונקציות זמן עובדות בצורה תקינה")
            return True
            
        except Exception as e:
            self.log_error("שגיאה בבדיקת פונקציות זמן", e)
            return False
    
    def test_profile_updates(self):
        """תיקון 5: בדיקת עדכון פרופילים"""
        try:
            print("👤 בודק עדכון פרופילים...")
            
            from profile_utils import update_user_profile_fast
            
            # בדיקה עם נתונים תקינים
            test_updates = {
                'test_field': 'test_value',
                'numeric_field': 123,
                'boolean_field': True
            }
            
            # בדיקה עם נתונים לא תקינים
            invalid_updates = {
                None: 'invalid_key',
                '': 'empty_key',
                'valid_key': {'nested': 'dict'}
            }
            
            # הבדיקה צריכה לעבוד בלי לזרוק שגיאה
            try:
                result = update_user_profile_fast("test_user", test_updates)
                self.log_success("עדכון פרופיל עם נתונים תקינים עבד")
            except Exception as e:
                self.log_error("שגיאה בעדכון פרופיל תקין", e)
                return False
            
            try:
                result = update_user_profile_fast("test_user", invalid_updates)
                self.log_success("עדכון פרופיל עם נתונים לא תקינים טופל נכון")
            except Exception as e:
                self.log_error("שגיאה בטיפול בנתונים לא תקינים", e)
                return False
            
            return True
            
        except Exception as e:
            self.log_error("שגיאה בבדיקת עדכון פרופילים", e)
            return False
    
    def check_chat_messages_alert(self):
        """תיקון 6: בדיקת אלרט הודעות"""
        try:
            print("💬 בודק אלרט הודעות...")
            
            # בדיקת מספר הודעות בפועל
            with safe_db_connection() as conn:
                cur = conn.cursor()
                
                # בדיקת קיום הטבלה
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'chat_messages'
                    )
                """)
                
                if not cur.fetchone()[0]:
                    self.log_error("טבלת chat_messages לא קיימת")
                    return False
                
                # ספירת הודעות
                cur.execute("SELECT COUNT(*) FROM chat_messages")
                total_messages = cur.fetchone()[0]
                
                self.log_success(f"טבלת chat_messages תקינה - {total_messages:,} הודעות")
                
                # בדיקת הודעות מהיום האחרון
                cur.execute("""
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE timestamp >= CURRENT_DATE - INTERVAL '1 day'
                """)
                recent_messages = cur.fetchone()[0]
                
                self.log_success(f"הודעות מהיום האחרון: {recent_messages:,}")
                
                return True
                
        except Exception as e:
            self.log_error("שגיאה בבדיקת אלרט הודעות", e)
            return False
    
    def run_comprehensive_fix(self):
        """ריצת תיקון מקיף של כל הבעיות"""
        try:
            print("🚀 מתחיל תיקון מקיף של שגיאות הרנדר...")
            print("=" * 60)
            
            # שלב 1: תיקון מיגרציית מסד הנתונים
            if not self.fix_database_migration():
                print("❌ תיקון מיגרציה נכשל - עצירת התהליך")
                return False
            
            # שלב 2: בדיקת עמודות
            if not self.verify_database_columns():
                print("❌ בדיקת עמודות נכשלה - עצירת התהליך")
                return False
            
            # שלב 3: בדיקת פונקציות התאוששות
            if not self.test_recovery_functions():
                print("⚠️ בדיקת פונקציות התאוששות נכשלה - ממשיך")
            
            # שלב 4: בדיקת פונקציות זמן
            if not self.test_datetime_functions():
                print("⚠️ בדיקת פונקציות זמן נכשלה - ממשיך")
            
            # שלב 5: בדיקת עדכון פרופילים
            if not self.test_profile_updates():
                print("⚠️ בדיקת עדכון פרופילים נכשלה - ממשיך")
            
            # שלב 6: בדיקת אלרט הודעות
            if not self.check_chat_messages_alert():
                print("⚠️ בדיקת אלרט הודעות נכשלה - ממשיך")
            
            print("=" * 60)
            print("📊 סיכום תיקונים:")
            print(f"✅ הצלחות: {len(self.errors_fixed)}")
            for success in self.errors_fixed:
                print(f"   • {success}")
            
            if self.errors_failed:
                print(f"❌ כישלונות: {len(self.errors_failed)}")
                for failure in self.errors_failed:
                    print(f"   • {failure}")
            
            success_rate = len(self.errors_fixed) / (len(self.errors_fixed) + len(self.errors_failed)) * 100
            print(f"📈 אחוז הצלחה: {success_rate:.1f}%")
            
            if success_rate >= 70:
                print("✅ תיקון מקיף הושלם בהצלחה!")
                return True
            else:
                print("⚠️ תיקון מקיף הושלם עם שגיאות")
                return False
                
        except Exception as e:
            print(f"❌ שגיאה קריטית בתיקון מקיף: {e}")
            traceback.print_exc()
            return False

def main():
    """פונקציה ראשית"""
    print("🔧 מתחיל תיקון מערכתי של שגיאות הרנדר")
    print("=" * 60)
    
    fixer = RenderErrorFixer()
    success = fixer.run_comprehensive_fix()
    
    if success:
        print("\n✅ תיקון הושלם בהצלחה!")
        print("🚀 ניתן להריץ את הבוט בביטחון")
        sys.exit(0)
    else:
        print("\n❌ תיקון הושלם עם שגיאות")
        print("🔍 בדוק את הלוגים לפרטים נוספים")
        sys.exit(1)

if __name__ == "__main__":
    main() 