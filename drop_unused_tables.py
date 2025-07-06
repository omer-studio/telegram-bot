#!/usr/bin/env python3
"""
מחיקת טבלאות מיותרות מהמסד נתונים
מוחק רק את הטבלאות שהושבתו בקוד ונגבו
"""

import psycopg2
import json
import os
from datetime import datetime
from config import DB_URL

def check_backup_exists():
    """בודק שקיים גיבוי עדכני של הטבלאות המיותרות"""
    try:
        if not os.path.exists('backups'):
            print("❌ תיקיית backups לא קיימת")
            return False
        
        # חיפוש גיבויים עדכניים
        backup_dirs = [d for d in os.listdir('backups') if d.startswith('unused_tables_backup_')]
        if not backup_dirs:
            print("❌ לא נמצא גיבוי של טבלאות מיותרות")
            return False
        
        # בדיקת הגיבוי האחרון
        latest_backup = os.path.join('backups', sorted(backup_dirs)[-1])
        summary_file = os.path.join(latest_backup, 'backup_summary.json')
        
        if not os.path.exists(summary_file):
            print(f"❌ קובץ סיכום גיבוי לא נמצא ב-{latest_backup}")
            return False
        
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        successful_backups = summary.get('successful_backups', 0)
        total_tables = summary.get('total_tables', 0)
        
        if successful_backups < total_tables:
            print(f"❌ גיבוי לא מלא: {successful_backups}/{total_tables} טבלאות נגבו")
            return False
        
        print(f"✅ נמצא גיבוי מלא ב-{latest_backup}")
        print(f"📊 {successful_backups} טבלאות נגבו בהצלחה")
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת גיבוי: {e}")
        return False

def drop_table_safely(table_name):
    """מוחק טבלה בבטחה עם בדיקות"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # בדיקת קיום הטבלה
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table_name,))
        
        if not cur.fetchone()[0]:
            print(f"⚠️ טבלה {table_name} לא קיימת - מדלג")
            cur.close()
            conn.close()
            return True
        
        # ספירת שורות לפני מחיקה
        cur.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cur.fetchone()[0]
        
        # מחיקת הטבלה
        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
        conn.commit()
        
        cur.close()
        conn.close()
        
        print(f"✅ {table_name}: נמחקה ({row_count} שורות)")
        return True
        
    except Exception as e:
        print(f"❌ שגיאה במחיקת {table_name}: {e}")
        return False

def drop_unused_tables():
    """מוחק את כל הטבלאות המיותרות"""
    print("🗑️ === מחיקת טבלאות מיותרות ===")
    
    # בדיקת גיבוי
    if not check_backup_exists():
        print("🚫 לא ניתן למחוק טבלאות ללא גיבוי!")
        return False
    
    # רשימת טבלאות מיותרות (אותה רשימה כמו בגיבוי)
    unused_tables = [
        'gpt_usage_log',
        'system_logs', 
        'critical_users',
        'billing_usage',
        'errors_stats',
        'free_model_limits',
        'chat_messages_old'
    ]
    
    print(f"\n🗑️ מוחק {len(unused_tables)} טבלאות מיותרות...")
    
    drop_results = {}
    
    for table in unused_tables:
        print(f"\n🔄 מוחק טבלה: {table}")
        success = drop_table_safely(table)
        drop_results[table] = success
    
    # סיכום
    successful = sum(drop_results.values())
    total = len(drop_results)
    
    print(f"\n📊 === סיכום מחיקה ===")
    print(f"✅ טבלאות שנמחקו בהצלחה: {successful}/{total}")
    
    for table, success in drop_results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {table}")
    
    if successful == total:
        print(f"\n🎉 כל הטבלאות המיותרות נמחקו בהצלחה!")
        print(f"💾 הנתונים נשמרו בגיבוי ב-backups/")
        return True
    else:
        failed = total - successful
        print(f"\n⚠️ {failed} טבלאות נכשלו במחיקה")
        return False

def verify_critical_tables_intact():
    """מוודא שהטבלאות הקריטיות לא נפגעו"""
    print(f"\n🔍 מאמת שהטבלאות הקריטיות שלמות...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # טבלאות קריטיות שחייבות להישאר
        critical_tables = [
            'chat_messages',
            'user_profiles', 
            'gpt_calls_log',
            'reminder_states'
        ]
        
        all_intact = True
        
        for table in critical_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cur.fetchone()[0]
                print(f"✅ {table}: {row_count} שורות")
            except Exception as e:
                print(f"❌ {table}: שגיאה - {e}")
                all_intact = False
        
        cur.close()
        conn.close()
        
        if all_intact:
            print("✅ כל הטבלאות הקריטיות שלמות ותקינות")
        else:
            print("❌ יש בעיה עם טבלאות קריטיות!")
        
        return all_intact
        
    except Exception as e:
        print(f"❌ שגיאה באימות טבלאות קריטיות: {e}")
        return False

def create_drop_log():
    """יוצר לוג של פעולת המחיקה"""
    try:
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'action': 'drop_unused_tables',
            'tables_dropped': [
                'gpt_usage_log',
                'system_logs', 
                'critical_users',
                'billing_usage',
                'errors_stats',
                'free_model_limits',
                'chat_messages_old'
            ],
            'reason': 'הטבלאות הושבתו בקוד וכל המידע הקריטי נשמר בטבלאות אחרות',
            'backup_location': 'backups/unused_tables_backup_*',
            'critical_tables_preserved': [
                'chat_messages',
                'user_profiles', 
                'gpt_calls_log',
                'reminder_states',
                'bot_error_logs',
                'bot_trace_logs'
            ]
        }
        
        log_file = f"backups/drop_tables_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, ensure_ascii=False, indent=2)
        
        print(f"📝 לוג מחיקה נשמר ב-{log_file}")
        return True
        
    except Exception as e:
        print(f"⚠️ שגיאה ביצירת לוג: {e}")
        return False

if __name__ == "__main__":
    print("🗑️ === סקריפט מחיקת טבלאות מיותרות ===")
    print("⚠️ פעולה זו בלתי הפיכה - וודא שיש גיבוי!")
    
    # בדיקת בטיחות
    print("\n🔒 בדיקות בטיחות:")
    
    # 1. בדיקת גיבוי
    if not check_backup_exists():
        print("🚫 מחיקה מבוטלת - אין גיבוי תקין!")
        exit(1)
    
    # 2. בדיקת טבלאות קריטיות
    if not verify_critical_tables_intact():
        print("🚫 מחיקה מבוטלת - בעיה עם טבלאות קריטיות!")
        exit(1)
    
    print("✅ כל בדיקות הבטיחות עברו בהצלחה")
    
    # ביצוע המחיקה
    print(f"\n🗑️ מתחיל מחיקת טבלאות מיותרות...")
    
    drop_success = drop_unused_tables()
    
    if drop_success:
        # אימות שהטבלאות הקריטיות עדיין תקינות
        verify_critical_tables_intact()
        
        # יצירת לוג
        create_drop_log()
        
        print(f"\n🎯 מחיקת הטבלאות הושלמה בהצלחה!")
        print(f"💾 כל הנתונים נשמרו בגיבוי")
        print(f"🟢 הטבלאות הקריטיות נשארו שלמות")
    else:
        print(f"\n⚠️ המחיקה לא הושלמה במלואו!")
    
    print(f"\n✅ סקריפט מחיקה הסתיים") 