#!/usr/bin/env python3
"""
🔒 מערכת גיבוי אוטומטי יומי לטבלאות קריטיות
הרץ יומית ב-3:00 בלילה ושומר גיבויים
"""

import os
import json
import psycopg2
from datetime import datetime, timedelta
from config import config
from simple_logger import logger

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
BACKUP_DIR = "backups/daily_db_backups"

# 🔒 טבלאות קריטיות שחובה לגבות
CRITICAL_TABLES = [
    "user_profiles",     # הלב של המערכת - קודי אישור ומשתמשים
    "chat_messages",     # כל היסטוריית השיחות
    "gpt_calls_log"      # כל הקריאות והעלויות
]

def ensure_backup_dir():
    """יוצר תיקיית גיבויים אם לא קיימת"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

def backup_table_to_json(table_name, backup_date):
    """מגבה טבלה יחידה לקובץ JSON"""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # שליפת כל הנתונים מהטבלה
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        
        # שליפת שמות העמודות
        cur.execute(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        
        # המרה ל-JSON
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                # המרת datetime לstring
                if isinstance(value, datetime):
                    value = value.isoformat()
                row_dict[col] = value
            data.append(row_dict)
        
        # שמירת הגיבוי
        backup_file = f"{BACKUP_DIR}/{table_name}_{backup_date}.json"
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        
        cur.close()
        conn.close()
        
        logger.info(f"✅ גיבוי {table_name}: {len(data)} שורות נשמרו ל-{backup_file}")
        return len(data)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי {table_name}: {e}")
        return 0

def create_backup_summary(backup_date, results):
    """יוצר קובץ סיכום לגיבוי"""
    summary = {
        "backup_date": backup_date,
        "backup_time": datetime.now().isoformat(),
        "tables_backed_up": len(results),
        "total_rows": sum(results.values()),
        "results": results,
        "backup_location": BACKUP_DIR
    }
    
    summary_file = f"{BACKUP_DIR}/backup_summary_{backup_date}.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    return summary

def cleanup_old_backups(days_to_keep=30):
    """מחיקת גיבויים ישנים (שומר רק 30 ימים אחרונים)"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        for filename in os.listdir(BACKUP_DIR):
            file_path = os.path.join(BACKUP_DIR, filename)
            if os.path.isfile(file_path):
                # בדיקת תאריך הקובץ
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_time < cutoff_date:
                    os.remove(file_path)
                    logger.info(f"🗑️ נמחק גיבוי ישן: {filename}")
                    
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי גיבויים ישנים: {e}")

def run_daily_backup():
    """מריץ גיבוי יומי מלא"""
    try:
        logger.info("🔒 מתחיל גיבוי יומי של טבלאות קריטיות")
        
        # הכנת תיקיית גיבויים
        ensure_backup_dir()
        
        # תאריך לשם הקובץ
        backup_date = datetime.now().strftime("%Y%m%d")
        
        # גיבוי כל טבלה קריטית
        backup_results = {}
        for table in CRITICAL_TABLES:
            rows_backed_up = backup_table_to_json(table, backup_date)
            backup_results[table] = rows_backed_up
        
        # יצירת סיכום
        summary = create_backup_summary(backup_date, backup_results)
        
        # ניקוי גיבויים ישנים
        cleanup_old_backups()
        
        logger.info(f"✅ גיבוי יומי הושלם: {summary['total_rows']} שורות נשמרו")
        print(f"✅ גיבוי יומי הושלם: {summary['total_rows']} שורות נשמרו")
        
        return summary
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי יומי: {e}")
        print(f"❌ שגיאה בגיבוי יומי: {e}")
        return None

def restore_table_from_backup(table_name, backup_date):
    """שחזור טבלה מגיבוי (למקרי חירום)"""
    try:
        backup_file = f"{BACKUP_DIR}/{table_name}_{backup_date}.json"
        
        if not os.path.exists(backup_file):
            print(f"❌ קובץ גיבוי לא נמצא: {backup_file}")
            return False
        
        # קריאת הגיבוי
        with open(backup_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        print(f"⚠️  האם אתה בטוח שאתה רוצה לשחזר {table_name} מ-{backup_date}?")
        print(f"⚠️  זה ימחק את כל הנתונים הנוכחיים בטבלה!")
        print(f"📊 גיבוי מכיל: {len(backup_data)} שורות")
        
        confirm = input("הקלד 'YES' כדי לאשר: ")
        if confirm != "YES":
            print("❌ שחזור בוטל")
            return False
        
        # ביצוע השחזור
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # מחיקת נתונים נוכחיים
        cur.execute(f"DELETE FROM {table_name}")
        
        # שחזור הנתונים
        if backup_data:
            columns = list(backup_data[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            
            insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            
            for row in backup_data:
                values = [row[col] for col in columns]
                cur.execute(insert_sql, values)
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ שחזור הושלם: {len(backup_data)} שורות")
        logger.info(f"✅ שחזור {table_name} מ-{backup_date}: {len(backup_data)} שורות")
        
        return True
        
    except Exception as e:
        print(f"❌ שגיאה בשחזור: {e}")
        logger.error(f"❌ שגיאה בשחזור {table_name}: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        if len(sys.argv) < 4:
            print("שימוש: python daily_backup.py restore <table_name> <backup_date>")
            print("דוגמה: python daily_backup.py restore user_profiles 20250109")
        else:
            table_name = sys.argv[2]
            backup_date = sys.argv[3]
            restore_table_from_backup(table_name, backup_date)
    else:
        # גיבוי רגיל
        run_daily_backup() 