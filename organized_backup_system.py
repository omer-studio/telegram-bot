#!/usr/bin/env python3
"""
🗂️ מערכת גיבוי מסודרת ברמת OCD
יוצרת מבנה תיקיות מושלם עם קבצים יומיים לכל טבלה
כל טבלה בתיקיה נפרדת עם קבצי JSON יומיים
"""

import os
import json
import psycopg2
from datetime import datetime, timedelta
from decimal import Decimal
from config import config
from simple_logger import logger
from admin_notifications import send_admin_notification

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

# 🎯 הגדרות גיבוי מסודר
BACKUP_ROOT = "backups/organized_backups"
TABLES_CONFIG = {
    "user_profiles": {
        "folder": "user_profile_backup",
        "filename_prefix": "user_profile_backup"
    },
    "chat_messages": {
        "folder": "chat_history_backup", 
        "filename_prefix": "chat_history_backup"
    },
    "gpt_calls_log": {
        "folder": "gpt_calls_backup",
        "filename_prefix": "gpt_calls_backup"
    }
}

def setup_organized_backup_structure():
    """יוצר את מבנה התיקיות המסודר"""
    try:
        # יצירת תיקיית שורש
        os.makedirs(BACKUP_ROOT, exist_ok=True)
        
        # יצירת תיקיה לכל טבלה
        for table_name, config in TABLES_CONFIG.items():
            folder_path = os.path.join(BACKUP_ROOT, config["folder"])
            os.makedirs(folder_path, exist_ok=True)
            logger.info(f"📁 תיקיה מוכנה: {folder_path}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה ביצירת מבנה תיקיות: {e}")
        return False

def safe_json_serializer(obj):
    """ממיר אובייקטים לJSON בצורה בטוחה"""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return str(obj)

def backup_table_to_organized_file(table_name, backup_date):
    """מגבה טבלה לקובץ JSON מסודר"""
    try:
        if table_name not in TABLES_CONFIG:
            logger.error(f"❌ טבלה {table_name} לא מוגדרת בתצורה")
            return None
        
        config_data = TABLES_CONFIG[table_name]
        folder_path = os.path.join(BACKUP_ROOT, config_data["folder"])
        filename = f"{config_data['filename_prefix']}_{backup_date}.json"
        file_path = os.path.join(folder_path, filename)
        
        # חיבור למסד נתונים
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        # שליפת הנתונים
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        
        # שליפת שמות עמודות
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        columns = [row[0] for row in cur.fetchall()]
        
        # המרה לרשימת מילונים
        data_list = []
        for row in rows:
            row_dict = {}
            for i, column in enumerate(columns):
                row_dict[column] = row[i]
            data_list.append(row_dict)
        
        # יצירת מטא-מידע
        backup_time = datetime.now()
        metadata = {
            "backup_date": backup_date,
            "backup_timestamp": backup_time.isoformat(),
            "table_name": table_name,
            "records_count": len(data_list),
            "columns": columns,
            "backup_system": "organized_backup_v2",
            "confirmation_code": f"BK-{table_name.upper()[:3]}-{backup_date}-{len(data_list):04d}"
        }
        
        # הכנת המבנה הסופי
        backup_structure = {
            "metadata": metadata,
            "data": data_list
        }
        
        # שמירה לקובץ
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(backup_structure, f, ensure_ascii=False, indent=2, default=safe_json_serializer)
        
        # קבלת גודל קובץ
        file_size = os.path.getsize(file_path)
        
        cur.close()
        conn.close()
        
        backup_info = {
            "table_name": table_name,
            "file_path": file_path,
            "records_count": len(data_list),
            "file_size_bytes": file_size,
            "file_size_mb": file_size / 1024 / 1024,
            "confirmation_code": metadata["confirmation_code"],
            "backup_timestamp": backup_time
        }
        
        logger.info(f"✅ {table_name}: {len(data_list)} רשומות → {file_size/1024:.1f}KB")
        return backup_info
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי {table_name}: {e}")
        return None

def run_organized_backup():
    """מריץ גיבוי מסודר מלא"""
    try:
        backup_date = datetime.now().strftime("%d_%m_%Y")
        logger.info(f"🗂️ מתחיל גיבוי מסודר לתאריך {backup_date}")
        
        # הכנת מבנה תיקיות
        if not setup_organized_backup_structure():
            return False
        
        # גיבוי כל טבלה
        backup_results = {}
        total_records = 0
        total_size_bytes = 0
        
        for table_name in TABLES_CONFIG.keys():
            backup_info = backup_table_to_organized_file(table_name, backup_date)
            
            if backup_info:
                backup_results[table_name] = backup_info
                total_records += backup_info["records_count"]
                total_size_bytes += backup_info["file_size_bytes"]
        
        # בדיקת הצלחה
        if len(backup_results) == len(TABLES_CONFIG):
            logger.info(f"🎉 גיבוי מסודר הושלם: {total_records} רשומות ב-{len(backup_results)} קבצים")
            
            # השוואה ליום קודם
            yesterday_comparison = compare_with_yesterday(backup_date, backup_results)
            
            # שליחת התראה מפורטת
            send_detailed_organized_backup_notification(backup_results, total_records, total_size_bytes, yesterday_comparison)
            
            return True
        else:
            logger.error(f"❌ גיבוי מסודר נכשל: {len(backup_results)}/{len(TABLES_CONFIG)} טבלאות")
            return False
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי מסודר: {e}")
        return False

def compare_with_yesterday(today_date, today_results):
    """משווה את הגיבוי של היום עם אמש"""
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%d_%m_%Y")
        comparison = {}
        
        for table_name, today_info in today_results.items():
            config_data = TABLES_CONFIG[table_name]
            folder_path = os.path.join(BACKUP_ROOT, config_data["folder"])
            yesterday_filename = f"{config_data['filename_prefix']}_{yesterday}.json"
            yesterday_file_path = os.path.join(folder_path, yesterday_filename)
            
            if os.path.exists(yesterday_file_path):
                try:
                    with open(yesterday_file_path, 'r', encoding='utf-8') as f:
                        yesterday_data = json.load(f)
                    
                    yesterday_records = yesterday_data["metadata"]["records_count"]
                    yesterday_size = os.path.getsize(yesterday_file_path)
                    
                    comparison[table_name] = {
                        "yesterday_records": yesterday_records,
                        "today_records": today_info["records_count"],
                        "records_diff": today_info["records_count"] - yesterday_records,
                        "yesterday_size_mb": yesterday_size / 1024 / 1024,
                        "today_size_mb": today_info["file_size_mb"],
                        "size_diff_mb": today_info["file_size_mb"] - (yesterday_size / 1024 / 1024)
                    }
                    
                except Exception as e:
                    logger.warning(f"⚠️ לא ניתן לקרוא גיבוי של אמש עבור {table_name}: {e}")
            else:
                comparison[table_name] = {
                    "yesterday_records": 0,
                    "today_records": today_info["records_count"],
                    "records_diff": today_info["records_count"],
                    "yesterday_size_mb": 0,
                    "today_size_mb": today_info["file_size_mb"],
                    "size_diff_mb": today_info["file_size_mb"]
                }
        
        return comparison
        
    except Exception as e:
        logger.warning(f"⚠️ שגיאה בהשוואה עם אמש: {e}")
        return {}

def send_detailed_organized_backup_notification(backup_results, total_records, total_size_bytes, yesterday_comparison):
    """שולח התראה מפורטת על הגיבוי המסודר"""
    try:
        backup_time = datetime.now()
        
        # כותרת ההודעה
        notification = f"🗂️ **גיבוי מסודר הושלם בהצלחה**\n\n"
        notification += f"📅 **תאריך:** {backup_time.strftime('%d/%m/%Y')}\n"
        notification += f"🕐 **שעה:** {backup_time.strftime('%H:%M:%S')}\n"
        notification += f"📊 **סה\"כ רשומות:** {total_records:,}\n"
        notification += f"💾 **סה\"כ גודל:** {total_size_bytes/1024/1024:.2f} MB\n"
        notification += f"📁 **מספר קבצים:** {len(backup_results)}\n\n"
        
        # פירוט לכל טבלה
        notification += f"📋 **פירוט מפורט:**\n"
        for table_name, info in backup_results.items():
            notification += f"\n🔹 **{table_name}:**\n"
            notification += f"   📊 רשומות: {info['records_count']:,}\n"
            notification += f"   💾 גודל: {info['file_size_mb']:.2f} MB\n"
            notification += f"   🔒 קוד אישור: `{info['confirmation_code']}`\n"
            notification += f"   📁 קובץ: `{os.path.basename(info['file_path'])}`\n"
            
            # השוואה עם אמש
            if table_name in yesterday_comparison:
                comp = yesterday_comparison[table_name]
                records_change = comp["records_diff"]
                size_change = comp["size_diff_mb"]
                
                if records_change > 0:
                    notification += f"   📈 שינוי: +{records_change} רשומות (+{size_change:.2f} MB)\n"
                elif records_change < 0:
                    notification += f"   📉 שינוי: {records_change} רשומות ({size_change:.2f} MB)\n"
                else:
                    notification += f"   ➖ אין שינוי מאמש\n"
        
        # מיקום הקבצים
        notification += f"\n📂 **מיקום הקבצים:**\n"
        notification += f"```\n{BACKUP_ROOT}/\n"
        for table_name, config_data in TABLES_CONFIG.items():
            notification += f"├── {config_data['folder']}/\n"
        notification += f"```\n"
        
        # שמירה ל-30 ימים
        notification += f"\n🗓️ **מדיניות שמירה:** 30 ימים אחרונים\n"
        notification += f"🧹 **ניקוי אוטומטי:** קבצים ישנים מ-30 ימים"
        
        send_admin_notification(notification)
        
    except Exception as e:
        logger.error(f"❌ שגיאה בשליחת התראה מפורטת: {e}")

def list_organized_backups():
    """מציג רשימת גיבויים מסודרים"""
    try:
        if not os.path.exists(BACKUP_ROOT):
            print("📭 אין תיקיית גיבויים מסודרים")
            return
        
        print("🗂️ גיבויים מסודרים זמינים:")
        print("=" * 60)
        
        # עבור כל תיקיית טבלה
        for table_name, config_data in TABLES_CONFIG.items():
            folder_path = os.path.join(BACKUP_ROOT, config_data["folder"])
            
            if not os.path.exists(folder_path):
                continue
            
            print(f"\n📂 {config_data['folder']}/")
            
            # קריאת כל הקבצים בתיקיה
            files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
            files.sort(reverse=True)  # הכי חדשים קודם
            
            if not files:
                print("   📭 אין קבצי גיבוי")
                continue
            
            for filename in files[:10]:  # הצג עד 10 אחרונים
                file_path = os.path.join(folder_path, filename)
                
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    metadata = data.get("metadata", {})
                    records_count = metadata.get("records_count", 0)
                    backup_date = metadata.get("backup_date", "unknown")
                    confirmation_code = metadata.get("confirmation_code", "N/A")
                    
                    file_size = os.path.getsize(file_path)
                    
                    print(f"   📄 {filename}")
                    print(f"      📅 {backup_date} | 📊 {records_count:,} רשומות | 💾 {file_size/1024:.1f}KB")
                    print(f"      🔒 {confirmation_code}")
                    
                except Exception as e:
                    print(f"   ❌ שגיאה בקריאת {filename}: {e}")
            
            if len(files) > 10:
                print(f"   ... ועוד {len(files) - 10} קבצים")
        
    except Exception as e:
        print(f"❌ שגיאה בצפייה בגיבויים: {e}")
        logger.error(f"❌ שגיאה בצפייה בגיבויים: {e}")

def cleanup_old_organized_backups(days_to_keep=30):
    """מנקה גיבויים מסודרים ישנים"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        deleted_files = 0
        
        for table_name, config_data in TABLES_CONFIG.items():
            folder_path = os.path.join(BACKUP_ROOT, config_data["folder"])
            
            if not os.path.exists(folder_path):
                continue
            
            files = [f for f in os.listdir(folder_path) if f.endswith('.json')]
            
            for filename in files:
                file_path = os.path.join(folder_path, filename)
                
                try:
                    # בדיקת תאריך הקובץ
                    file_date_str = filename.split('_')[-3:]  # dd_mm_yyyy.json
                    if len(file_date_str) == 3:
                        file_date_str = '_'.join(file_date_str).replace('.json', '')
                        file_date = datetime.strptime(file_date_str, "%d_%m_%Y")
                        
                        if file_date < cutoff_date:
                            os.remove(file_path)
                            deleted_files += 1
                            logger.info(f"🗑️ נמחק קובץ ישן: {filename}")
                
                except Exception as e:
                    logger.warning(f"⚠️ שגיאה בבדיקת תאריך {filename}: {e}")
        
        if deleted_files > 0:
            logger.info(f"🧹 נמחקו {deleted_files} קבצי גיבוי ישנים")
            
            send_admin_notification(
                f"🧹 **ניקוי גיבויים מסודרים**\n\n" +
                f"🗑️ **נמחקו:** {deleted_files} קבצים\n" +
                f"📅 **ישנים מ:** {cutoff_date.strftime('%d/%m/%Y')}\n" +
                f"💾 **שמירת:** {days_to_keep} ימים אחרונים"
            )
        else:
            logger.info("🧹 אין קבצי גיבוי ישנים למחיקה")
        
    except Exception as e:
        logger.error(f"❌ שגיאה בניקוי גיבויים: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "backup":
            run_organized_backup()
        elif command == "list":
            list_organized_backups()
        elif command == "cleanup":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            cleanup_old_organized_backups(days)
        else:
            print("שימוש: python organized_backup_system.py [backup|list|cleanup]")
    else:
        # גיבוי רגיל
        run_organized_backup() 