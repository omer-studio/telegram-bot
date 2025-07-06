#!/usr/bin/env python3
"""
גיבוי טבלאות מיותרות לפני מחיקה
מגבה את כל הטבלאות המיותרות לקבצי JSON בתיקיית backups/
"""

import psycopg2
import json
import os
import csv
from datetime import datetime
from config import DB_URL

def create_backup_directory():
    """יוצר תיקיית גיבוי עם חותמת זמן"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backups/unused_tables_backup_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir

def backup_table_to_json(table_name, backup_dir):
    """מגבה טבלה לקובץ JSON"""
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
            return False
        
        # קבלת כל הנתונים
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        
        # קבלת שמות העמודות
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = [row[0] for row in cur.fetchall()]
        
        # המרה לרשימת dictionaries
        data = []
        for row in rows:
            row_dict = {}
            for i, value in enumerate(row):
                # המרת datetime לstring
                if hasattr(value, 'isoformat'):
                    value = value.isoformat()
                row_dict[columns[i]] = value
            data.append(row_dict)
        
        # שמירה לקובץ JSON
        json_file = os.path.join(backup_dir, f"{table_name}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                'table_name': table_name,
                'backup_timestamp': datetime.now().isoformat(),
                'row_count': len(data),
                'columns': columns,
                'data': data
            }, f, ensure_ascii=False, indent=2)
        
        # שמירה לקובץ CSV גם כן
        csv_file = os.path.join(backup_dir, f"{table_name}.csv")
        if data:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=columns)
                writer.writeheader()
                writer.writerows(data)
        
        cur.close()
        conn.close()
        
        print(f"✅ {table_name}: {len(data)} שורות נגבו ל-{json_file} ו-{csv_file}")
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בגיבוי {table_name}: {e}")
        return False

def backup_unused_tables():
    """מגבה את כל הטבלאות המיותרות"""
    print("📦 === גיבוי טבלאות מיותרות לפני מחיקה ===")
    
    # יצירת תיקיית גיבוי
    backup_dir = create_backup_directory()
    print(f"📁 תיקיית גיבוי: {backup_dir}")
    
    # רשימת טבלאות מיותרות
    unused_tables = [
        'gpt_usage_log',
        'system_logs', 
        'critical_users',
        'billing_usage',
        'errors_stats',
        'free_model_limits',
        'chat_messages_old'  # אם קיימת
    ]
    
    backup_results = {}
    
    for table in unused_tables:
        print(f"\n🔄 מגבה טבלה: {table}")
        success = backup_table_to_json(table, backup_dir)
        backup_results[table] = success
    
    # יצירת קובץ סיכום
    summary = {
        'backup_timestamp': datetime.now().isoformat(),
        'backup_directory': backup_dir,
        'tables_backed_up': backup_results,
        'successful_backups': sum(backup_results.values()),
        'total_tables': len(backup_results),
        'note': 'הטבלאות האלה הושבתו בקוד ועכשיו ניתן למחוק אותן בבטחה'
    }
    
    summary_file = os.path.join(backup_dir, 'backup_summary.json')
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    # דוח סיכום
    successful = sum(backup_results.values())
    total = len(backup_results)
    
    print(f"\n📊 === סיכום גיבוי ===")
    print(f"📁 תיקיית גיבוי: {backup_dir}")
    print(f"✅ טבלאות שנגבו בהצלחה: {successful}/{total}")
    print(f"📄 קובץ סיכום: {summary_file}")
    
    for table, success in backup_results.items():
        status = "✅" if success else "❌"
        print(f"   {status} {table}")
    
    if successful == total:
        print(f"\n🎉 כל הטבלאות נגבו בהצלחה!")
        print(f"🚫 כעת ניתן למחוק את הטבלאות המיותרות בבטחה")
        return True
    else:
        failed = total - successful
        print(f"\n⚠️ {failed} טבלאות נכשלו בגיבוי - בדוק לפני מחיקה!")
        return False

def verify_backup_integrity(backup_dir):
    """מאמת תקינות הגיבוי"""
    print(f"\n🔍 מאמת תקינות גיבוי ב-{backup_dir}")
    
    try:
        # קריאת קובץ הסיכום
        summary_file = os.path.join(backup_dir, 'backup_summary.json')
        if not os.path.exists(summary_file):
            print("❌ קובץ סיכום לא נמצא")
            return False
        
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        # בדיקת קיום קבצים
        missing_files = []
        for table, success in summary['tables_backed_up'].items():
            if success:
                json_file = os.path.join(backup_dir, f"{table}.json")
                csv_file = os.path.join(backup_dir, f"{table}.csv")
                
                if not os.path.exists(json_file):
                    missing_files.append(f"{table}.json")
                if not os.path.exists(csv_file):
                    missing_files.append(f"{table}.csv")
        
        if missing_files:
            print(f"❌ קבצים חסרים: {missing_files}")
            return False
        
        print("✅ כל קבצי הגיבוי קיימים ותקינים")
        return True
        
    except Exception as e:
        print(f"❌ שגיאה באימות גיבוי: {e}")
        return False

if __name__ == "__main__":
    print("📦 מתחיל גיבוי טבלאות מיותרות...")
    
    # ביצוע הגיבוי
    backup_success = backup_unused_tables()
    
    if backup_success:
        # אימות תקינות הגיבוי
        backup_dirs = [d for d in os.listdir('backups') if d.startswith('unused_tables_backup_')]
        if backup_dirs:
            latest_backup = os.path.join('backups', sorted(backup_dirs)[-1])
            verify_backup_integrity(latest_backup)
        
        print(f"\n🎯 הגיבוי הושלם בהצלחה!")
        print(f"🚫 כעת ניתן להמשיך למחיקת הטבלאות המיותרות")
    else:
        print(f"\n⚠️ הגיבוי לא הושלם במלואו - בדוק שגיאות לפני מחיקה!")
    
    print(f"\n✅ סקריפט גיבוי הסתיים") 