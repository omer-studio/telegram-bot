#!/usr/bin/env python3
"""
🔒 backup_system.py
==================
מערכת גיבוי מאוחדת - מחליפה 12 קבצי גיבוי שונים!

🎯 מחלקות:
- LocalBackup: גיבוי יומי לקבצי JSON
- CloudBackup: גיבוי ענן למסד נתונים נפרד  
- InternalBackup: גיבוי פנימי במסד הנתונים
- S3Backup: גיבוי ל-AWS S3
- DualBackup: גיבוי כפול ל-Dropbox + OneDrive
- RestoreManager: שחזור מכל המקורות
- BackupScheduler: תזמון גיבויים
- BackupManager: ניהול מרכזי של כל הגיבויים

🔄 מחליף:
- daily_backup.py, cloud_backup.py, organized_internal_backup.py
- aws_s3_backup.py, simple_dual_backup.py, enhanced_backup_system.py
- comprehensive_chat_restore.py, emergency_full_restore.py
- schedule_internal_backup.py, internal_backup_system.py
- organized_backup_system.py, backup_unused_tables.py
"""

import os
import json
import psycopg2
import shutil
import hashlib
import boto3
import threading
import schedule
import atexit
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

from config import config
from simple_logger import logger
from admin_notifications import send_admin_notification
from database_operations import get_safe_db_connection

# 🔒 טבלאות קריטיות לגיבוי
CRITICAL_TABLES = [
    "user_profiles",     # הלב של המערכת - קודי אישור ומשתמשים
    "chat_messages",     # כל היסטוריית השיחות
    "interactions_log"   # כל הקריאות והעלויות
]

# 🎯 הגדרות גלובליות
DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
BACKUP_DB_URL = os.getenv("BACKUP_DATABASE_URL")
BACKUP_DIR = "backups/daily_db_backups"
BACKUP_SCHEMA = "backup"
BACKUP_RETENTION_DAYS = 30

class LocalBackup:
    """🔒 גיבוי יומי לקבצי JSON לוקליים"""
    
    def __init__(self, backup_dir: str = BACKUP_DIR):
        self.backup_dir = backup_dir
        self.ensure_backup_dir()
    
    def ensure_backup_dir(self):
        """יוצר תיקיית גיבויים אם לא קיימת"""
        os.makedirs(self.backup_dir, exist_ok=True)
    
    def backup_table_to_json(self, table_name: str, backup_date: str) -> int:
        """מגבה טבלה יחידה לקובץ JSON"""
        try:
            with get_safe_db_connection() as conn:
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
                        if isinstance(value, datetime):
                            value = value.isoformat()
                        row_dict[col] = value
                    data.append(row_dict)
                
                # שמירת הגיבוי
                backup_file = f"{self.backup_dir}/{table_name}_{backup_date}.json"
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, default=str)
                
                logger.info(f"✅ גיבוי {table_name}: {len(data)} שורות נשמרו ל-{backup_file}")
                return len(data)
                
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי {table_name}: {e}")
            return 0
    
    def create_backup_summary(self, backup_date: str, results: Dict[str, int]) -> Dict[str, Any]:
        """יוצר קובץ סיכום לגיבוי"""
        summary = {
            "backup_date": backup_date,
            "backup_time": datetime.now().isoformat(),
            "tables_backed_up": len(results),
            "total_rows": sum(results.values()),
            "results": results,
            "backup_location": self.backup_dir
        }
        
        summary_file = f"{self.backup_dir}/backup_summary_{backup_date}.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        return summary
    
    def cleanup_old_backups(self, days_to_keep: int = 30):
        """מחיקת גיבויים ישנים"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            for filename in os.listdir(self.backup_dir):
                file_path = os.path.join(self.backup_dir, filename)
                if os.path.isfile(file_path):
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if file_time < cutoff_date:
                        os.remove(file_path)
                        logger.info(f"🗑️ נמחק גיבוי ישן: {filename}")
                        
        except Exception as e:
            logger.error(f"❌ שגיאה בניקוי גיבויים ישנים: {e}")
    
    def run_backup(self) -> Optional[Dict[str, Any]]:
        """מריץ גיבוי יומי מלא"""
        try:
            logger.info("🔒 מתחיל גיבוי יומי של טבלאות קריטיות")
            
            backup_date = datetime.now().strftime("%Y%m%d")
            backup_results = {}
            
            for table in CRITICAL_TABLES:
                rows_backed_up = self.backup_table_to_json(table, backup_date)
                backup_results[table] = rows_backed_up
            
            summary = self.create_backup_summary(backup_date, backup_results)
            self.cleanup_old_backups()
            
            logger.info(f"✅ גיבוי יומי הושלם: {summary['total_rows']} שורות נשמרו")
            return summary
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי יומי: {e}")
            return None
    
    def restore_table_from_backup(self, table_name: str, backup_date: str) -> bool:
        """שחזור טבלה מגיבוי JSON"""
        try:
            backup_file = f"{self.backup_dir}/{table_name}_{backup_date}.json"
            
            if not os.path.exists(backup_file):
                print(f"❌ קובץ גיבוי לא נמצא: {backup_file}")
                return False
            
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            print(f"⚠️  שחזור {table_name} מ-{backup_date}?")
            print(f"📊 גיבוי מכיל: {len(backup_data)} שורות")
            
            confirm = input("הקלד 'YES' כדי לאשר: ")
            if confirm != "YES":
                print("❌ שחזור בוטל")
                return False
            
            with get_safe_db_connection() as conn:
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
            
            print(f"✅ שחזור הושלם: {len(backup_data)} שורות")
            logger.info(f"✅ שחזור {table_name} מ-{backup_date}: {len(backup_data)} שורות")
            return True
            
        except Exception as e:
            print(f"❌ שגיאה בשחזור: {e}")
            return False


class CloudBackup:
    """☁️ גיבוי ענן למסד נתונים נפרד"""
    
    def __init__(self, backup_db_url: str = BACKUP_DB_URL):
        self.backup_db_url = backup_db_url or DB_URL
        
    def setup_backup_database(self) -> str:
        """יוצר מסד נתונים לגיבויים במסד נפרד"""
        if not BACKUP_DB_URL:
            logger.warning("⚠️ BACKUP_DATABASE_URL לא מוגדר - משתמש במסד הראשי")
            return DB_URL
        
        try:
            conn = psycopg2.connect(self.backup_db_url)
            cur = conn.cursor()
            
            # יצירת טבלת גיבויים
            cur.execute("""
                CREATE TABLE IF NOT EXISTS database_backups (
                    id SERIAL PRIMARY KEY,
                    backup_date DATE NOT NULL,
                    table_name TEXT NOT NULL,
                    backup_data JSONB NOT NULL,
                    backup_size_mb DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    checksum TEXT,
                    UNIQUE(backup_date, table_name)
                )
            """)
            
            # יצירת אינדקסים
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_backups_date_table 
                ON database_backups(backup_date, table_name)
            """)
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info("✅ מסד גיבויים מוכן")
            return self.backup_db_url
            
        except Exception as e:
            logger.error(f"❌ שגיאה בהכנת מסד גיבויים: {e}")
            return DB_URL
    
    def calculate_checksum(self, data: List[Dict]) -> str:
        """מחשב checksum לנתונים"""
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()
    
    def backup_table_to_cloud(self, table_name: str, backup_date: str, data: List[Dict]) -> bool:
        """מגבה טבלה למסד ענן נפרד"""
        try:
            backup_db = self.setup_backup_database()
            conn = psycopg2.connect(backup_db)
            cur = conn.cursor()
            
            data_size_mb = len(json.dumps(data, default=str)) / (1024 * 1024)
            checksum = self.calculate_checksum(data)
            
            # שמירת הגיבוי (UPSERT)
            cur.execute("""
                INSERT INTO database_backups 
                (backup_date, table_name, backup_data, backup_size_mb, checksum)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (backup_date, table_name)
                DO UPDATE SET 
                    backup_data = EXCLUDED.backup_data,
                    backup_size_mb = EXCLUDED.backup_size_mb,
                    checksum = EXCLUDED.checksum,
                    created_at = CURRENT_TIMESTAMP
            """, (backup_date, table_name, json.dumps(data, default=str), data_size_mb, checksum))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"☁️ גיבוי ענן {table_name}: {len(data)} רשומות ({data_size_mb:.2f}MB)")
            return True
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי ענן {table_name}: {e}")
            return False
    
    def run_backup(self) -> bool:
        """מריץ גיבוי ענן מלא"""
        try:
            logger.info("☁️ מתחיל גיבוי ענן")
            
            backup_date = datetime.now().strftime("%Y-%m-%d")
            successful_backups = 0
            
            for table in CRITICAL_TABLES:
                try:
                    with get_safe_db_connection() as conn:
                        cur = conn.cursor()
                        
                        cur.execute(f"SELECT * FROM {table}")
                        rows = cur.fetchall()
                        
                        cur.execute(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = '{table}' 
                            ORDER BY ordinal_position
                        """)
                        columns = [row[0] for row in cur.fetchall()]
                        
                        data = []
                        for row in rows:
                            row_dict = {}
                            for i, col in enumerate(columns):
                                value = row[i]
                                if isinstance(value, datetime):
                                    value = value.isoformat()
                                row_dict[col] = value
                            data.append(row_dict)
                    
                    if self.backup_table_to_cloud(table, backup_date, data):
                        successful_backups += 1
                    
                except Exception as e:
                    logger.error(f"❌ שגיאה בגיבוי ענן {table}: {e}")
            
            success = successful_backups == len(CRITICAL_TABLES)
            if success:
                logger.info(f"☁️ גיבוי ענן הושלם: {successful_backups}/{len(CRITICAL_TABLES)} טבלאות")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי ענן: {e}")
            return False


class InternalBackup:
    """🗄️ גיבוי פנימי מסודר במסד הנתונים"""
    
    def __init__(self, schema_name: str = BACKUP_SCHEMA):
        self.schema_name = schema_name
        self.create_backup_schema()
    
    def create_backup_schema(self) -> bool:
        """יוצר את ה-schema לגיבוי אם לא קיים"""
        try:
            with get_safe_db_connection() as conn:
                cur = conn.cursor()
                cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema_name}")
                conn.commit()
            
            logger.info(f"✅ Schema {self.schema_name} מוכן")
            return True
            
        except Exception as e:
            logger.error(f"❌ שגיאה ביצירת backup schema: {e}")
            return False
    
    def backup_table_to_internal(self, table_name: str, backup_date: str) -> Optional[Dict[str, Any]]:
        """מגבה טבלה לטבלת גיבוי פנימית"""
        try:
            with get_safe_db_connection() as conn:
                cur = conn.cursor()
                
                backup_table_name = f"{table_name}_backup_{backup_date}"
                full_backup_table = f"{self.schema_name}.{backup_table_name}"
                
                # מחיקת הטבלה אם קיימת
                cur.execute(f"DROP TABLE IF EXISTS {full_backup_table}")
                
                # יצירת הטבלה החדשה עם נתוני הגיבוי
                cur.execute(f"""
                    CREATE TABLE {full_backup_table} AS 
                    SELECT *, 
                           '{backup_date}' as backup_date,
                           '{datetime.now().isoformat()}' as backup_timestamp
                    FROM {table_name}
                """)
                
                # קבלת מספר הרשומות וגודל
                cur.execute(f"SELECT COUNT(*) FROM {full_backup_table}")
                records_count = cur.fetchone()[0]
                
                cur.execute(f"""
                    SELECT pg_size_pretty(pg_total_relation_size('{full_backup_table}'))
                """)
                table_size = cur.fetchone()[0]
                
                conn.commit()
            
            backup_info = {
                "table_name": table_name,
                "backup_table_name": backup_table_name,
                "full_backup_table": full_backup_table,
                "records_count": records_count,
                "table_size": table_size,
                "backup_date": backup_date,
                "confirmation_code": f"IB-{table_name.upper()[:3]}-{backup_date}-{records_count:04d}",
                "backup_timestamp": datetime.now()
            }
            
            logger.info(f"✅ {table_name} → {backup_table_name}: {records_count} רשומות ({table_size})")
            return backup_info
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי פנימי {table_name}: {e}")
            return None
    
    def run_backup(self) -> bool:
        """מריץ גיבוי פנימי מסודר מלא"""
        try:
            backup_date = datetime.now().strftime("%d_%m_%Y")
            logger.info(f"🗄️ מתחיל גיבוי פנימי מסודר לתאריך {backup_date}")
            
            backup_results = {}
            total_records = 0
            
            for table_name in CRITICAL_TABLES:
                backup_info = self.backup_table_to_internal(table_name, backup_date)
                if backup_info:
                    backup_results[table_name] = backup_info
                    total_records += backup_info["records_count"]
            
            success = len(backup_results) == len(CRITICAL_TABLES)
            if success:
                logger.info(f"🎉 גיבוי פנימי מסודר הושלם: {total_records} רשומות ב-{len(backup_results)} טבלאות")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי פנימי מסודר: {e}")
            return False


class S3Backup:
    """🪣 גיבוי ל-AWS S3"""
    
    def __init__(self):
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.bucket_name = os.getenv("AWS_S3_BUCKET_NAME", "telegram-bot-backups")
        self.region = os.getenv("AWS_REGION", "us-east-1")
    
    def is_configured(self) -> bool:
        """בודק אם AWS מוגדר"""
        return bool(self.aws_access_key and self.aws_secret_key)
    
    def upload_to_s3(self, file_path: str, s3_key: str) -> bool:
        """מעלה קובץ ל-S3"""
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key,
                aws_secret_access_key=self.aws_secret_key,
                region_name=self.region
            )
            
            s3_client.upload_file(file_path, self.bucket_name, s3_key)
            logger.info(f"☁️ הועלה ל-S3: {s3_key}")
            return True
            
        except Exception as e:
            logger.error(f"❌ שגיאה בהעלאה ל-S3: {e}")
            return False
    
    def run_backup(self, backup_dir: str = BACKUP_DIR) -> bool:
        """מגבה את כל קבצי הגיבוי ל-S3"""
        if not self.is_configured():
            logger.warning("⚠️ AWS לא מוגדר - דולג על גיבוי S3")
            return False
        
        try:
            backup_date = datetime.now().strftime("%Y%m%d")
            
            if not os.path.exists(backup_dir):
                logger.error("❌ תיקיית גיבויים לא קיימת")
                return False
            
            uploaded_files = 0
            for filename in os.listdir(backup_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(backup_dir, filename)
                    s3_key = f"daily_backups/{backup_date}/{filename}"
                    
                    if self.upload_to_s3(file_path, s3_key):
                        uploaded_files += 1
            
            logger.info(f"☁️ גיבוי S3 הושלם: {uploaded_files} קבצים")
            return uploaded_files > 0
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי S3: {e}")
            return False


class DualBackup:
    """📁 גיבוי כפול - Dropbox + OneDrive"""
    
    def __init__(self, local_backup: LocalBackup):
        self.local_backup = local_backup
        self.onedrive_path = "C:/Users/ASUS/OneDrive"
    
    def copy_to_onedrive(self) -> bool:
        """מעתיק את הגיבויים ל-OneDrive"""
        try:
            source_dir = self.local_backup.backup_dir
            backup_date = datetime.now().strftime("%Y%m%d")
            target_dir = os.path.join(self.onedrive_path, "TelegramBot_Backups", backup_date)
            
            if not os.path.exists(source_dir):
                logger.error("❌ תיקיית גיבוי מקור לא קיימת")
                return False
            
            if not os.path.exists(self.onedrive_path):
                logger.error("❌ OneDrive לא נמצא")
                return False
            
            os.makedirs(target_dir, exist_ok=True)
            
            copied_files = 0
            total_size = 0
            
            for filename in os.listdir(source_dir):
                if filename.endswith('.json'):
                    source_file = os.path.join(source_dir, filename)
                    target_file = os.path.join(target_dir, filename)
                    
                    shutil.copy2(source_file, target_file)
                    
                    file_size = os.path.getsize(target_file)
                    total_size += file_size
                    copied_files += 1
                    
                    logger.info(f"📄 הועתק: {filename} ({file_size/1024/1024:.2f}MB)")
            
            if copied_files > 0:
                logger.info(f"📁 OneDrive: {copied_files} קבצים ({total_size/1024/1024:.2f}MB כולל)")
                return True
            else:
                logger.warning("⚠️ לא נמצאו קבצים להעתקה")
                return False
            
        except Exception as e:
            logger.error(f"❌ שגיאה בהעתקה ל-OneDrive: {e}")
            return False
    
    def run_backup(self) -> bool:
        """מריץ גיבוי כפול - Dropbox + OneDrive"""
        try:
            logger.info("📁 מתחיל גיבוי כפול (Dropbox + OneDrive)")
            
            # 1. גיבוי רגיל ל-Dropbox
            dropbox_success = self.local_backup.run_backup() is not None
            
            # 2. העתקה נוספת ל-OneDrive
            onedrive_success = self.copy_to_onedrive()
            
            return dropbox_success or onedrive_success
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי כפול: {e}")
            return False


class RestoreManager:
    """🔄 מנהל שחזור מכל המקורות"""
    
    def __init__(self, local_backup: LocalBackup, cloud_backup: CloudBackup):
        self.local_backup = local_backup
        self.cloud_backup = cloud_backup
    
    def restore_from_json_file(self, file_path: str, source_name: str) -> int:
        """שחזור מקובץ JSON"""
        try:
            if not os.path.exists(file_path):
                print(f"❌ קובץ לא נמצא: {file_path}")
                return 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            print(f"📄 {source_name}: {len(backup_data)} הודעות")
            
            if not backup_data:
                return 0
            
            # שחזור הודעות למסד
            restored_count = 0
            with get_safe_db_connection() as conn:
                cur = conn.cursor()
                
                for message in backup_data:
                    try:
                        # בדיקה אם ההודעה כבר קיימת
                        if 'message_id' in message and 'chat_id' in message:
                            cur.execute("""
                                SELECT 1 FROM chat_messages 
                                WHERE message_id = %s AND chat_id = %s
                            """, (message['message_id'], message['chat_id']))
                            
                            if not cur.fetchone():
                                # הוספת ההודעה
                                columns = list(message.keys())
                                placeholders = ', '.join(['%s'] * len(columns))
                                insert_sql = f"INSERT INTO chat_messages ({', '.join(columns)}) VALUES ({placeholders})"
                                values = [message[col] for col in columns]
                                cur.execute(insert_sql, values)
                                restored_count += 1
                    
                    except Exception as e:
                        logger.warning(f"⚠️ שגיאה בשחזור הודעה: {e}")
                        continue
                
                conn.commit()
            
            print(f"✅ {source_name}: שוחזרו {restored_count:,} הודעות")
            return restored_count
            
        except Exception as e:
            print(f"❌ שגיאה בשחזור {source_name}: {e}")
            return 0
    
    def comprehensive_restore(self) -> bool:
        """שחזור מקיף מכל המקורות"""
        try:
            print("🚨 מתחיל שחזור מקיף מכל המקורות...")
            print("=" * 60)
            
            total_restored = 0
            
            # מקורות שחזור
            restoration_sources = [
                ("backups/daily_db_backups/chat_messages_20250709.json", "daily_backup_09_07"),
                ("backups/data_backup_20250706_141212/chat_history.json", "old_backup_06_07"),
                ("extracted_chat_data_20250706_155957.json", "extracted_data_06_07")
            ]
            
            for file_path, source_name in restoration_sources:
                restored = self.restore_from_json_file(file_path, source_name)
                total_restored += restored
            
            print(f"\n🎉 סיכום שחזור מקיף:")
            print(f"   📊 סה\"כ הודעות ששוחזרו: {total_restored:,}")
            
            return total_restored > 0
            
        except Exception as e:
            print(f"❌ שגיאה בשחזור מקיף: {e}")
            return False


class BackupScheduler:
    """⏰ מתזמן גיבויים אוטומטיים"""
    
    def __init__(self, backup_manager: 'BackupManager'):
        self.backup_manager = backup_manager
        self.is_running = False
    
    def start_scheduler(self) -> bool:
        """מתחיל את מתזמן הגיבויים"""
        try:
            schedule.every().day.at("03:00").do(self.backup_manager.run_all_backups)
            schedule.every().sunday.at("02:00").do(self.backup_manager.cleanup_old_backups)
            
            self.is_running = True
            logger.info("⏰ מתזמן גיבויים הופעל")
            
            # הרצה ברקע
            def run_scheduler():
                while self.is_running:
                    schedule.run_pending()
                    import time
                    time.sleep(60)
            
            scheduler_thread = threading.Thread(target=run_scheduler)
            scheduler_thread.daemon = True
            scheduler_thread.start()
            
            atexit.register(self.stop_scheduler)
            return True
            
        except Exception as e:
            logger.error(f"❌ שגיאה בהפעלת מתזמן: {e}")
            return False
    
    def stop_scheduler(self):
        """עוצר את המתזמן"""
        self.is_running = False
        schedule.clear()
        logger.info("⏰ מתזמן גיבויים נעצר")
    
    def run_backup_now(self) -> bool:
        """מריץ גיבוי מיידי"""
        return self.backup_manager.run_all_backups()


class BackupManager:
    """🎯 מנהל מרכזי של כל מערכת הגיבוי"""
    
    def __init__(self):
        self.local_backup = LocalBackup()
        self.cloud_backup = CloudBackup()
        self.internal_backup = InternalBackup()
        self.s3_backup = S3Backup()
        self.dual_backup = DualBackup(self.local_backup)
        self.restore_manager = RestoreManager(self.local_backup, self.cloud_backup)
        self.scheduler = BackupScheduler(self)
    
    def run_all_backups(self) -> bool:
        """מריץ את כל סוגי הגיבוי"""
        try:
            logger.info("🚀 מתחיל גיבוי מלא של כל המערכת")
            
            backup_results = {
                "local": False,
                "cloud": False,
                "internal": False,
                "s3": False,
                "dual": False
            }
            
            # 1. גיבוי מקומי
            try:
                backup_results["local"] = self.local_backup.run_backup() is not None
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי מקומי: {e}")
            
            # 2. גיבוי ענן
            try:
                backup_results["cloud"] = self.cloud_backup.run_backup()
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי ענן: {e}")
            
            # 3. גיבוי פנימי
            try:
                backup_results["internal"] = self.internal_backup.run_backup()
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי פנימי: {e}")
            
            # 4. גיבוי S3 (אם מוגדר)
            try:
                if self.s3_backup.is_configured():
                    backup_results["s3"] = self.s3_backup.run_backup()
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי S3: {e}")
            
            # 5. גיבוי כפול
            try:
                backup_results["dual"] = self.dual_backup.run_backup()
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי כפול: {e}")
            
            # סיכום
            successful_backups = sum(backup_results.values())
            total_attempted = len([k for k, v in backup_results.items() if k != "s3" or self.s3_backup.is_configured()])
            
            logger.info(f"🎯 גיבוי הושלם: {successful_backups}/{total_attempted} סוגי גיבוי")
            
            # התראה לאדמין
            self.send_backup_notification(backup_results, successful_backups, total_attempted)
            
            return successful_backups > 0
            
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי מלא: {e}")
            return False
    
    def send_backup_notification(self, results: Dict[str, bool], successful: int, total: int):
        """שולח התראה על סטטוס הגיבוי"""
        try:
            status_icons = {True: "✅", False: "❌"}
            message = f"🚀 **גיבוי מלא הושלם**\n\n"
            
            backup_names = {
                "local": "גיבוי מקומי (JSON)",
                "cloud": "גיבוי ענן (מסד נפרד)",
                "internal": "גיבוי פנימי (schema)",
                "s3": "גיבוי AWS S3",
                "dual": "גיבוי כפול (OneDrive)"
            }
            
            for backup_type, success in results.items():
                if backup_type == "s3" and not self.s3_backup.is_configured():
                    continue
                icon = status_icons[success]
                name = backup_names[backup_type]
                message += f"{icon} **{name}**\n"
            
            message += f"\n📊 **תוצאות:** {successful}/{total} גיבויים הצליחו"
            
            if successful == 0:
                message += "\n🚨 **אזהרה:** כל הגיבויים נכשלו!"
                urgent = True
            elif successful < total:
                message += "\n⚠️ **אזהרה:** חלק מהגיבויים נכשלו"
                urgent = False
            else:
                message += "\n🎉 **מעולה:** כל הגיבויים הצליחו!"
                urgent = False
            
            send_admin_notification(message, urgent=urgent)
            
        except Exception as e:
            logger.error(f"❌ שגיאה בשליחת התראת גיבוי: {e}")
    
    def cleanup_old_backups(self):
        """מנקה גיבויים ישנים בכל המערכות"""
        try:
            logger.info("🧹 מתחיל ניקוי גיבויים ישנים")
            
            # ניקוי גיבויים מקומיים
            self.local_backup.cleanup_old_backups()
            
            logger.info("✅ ניקוי גיבויים הושלם")
            
        except Exception as e:
            logger.error(f"❌ שגיאה בניקוי גיבויים: {e}")
    
    def get_backup_status(self) -> Dict[str, Any]:
        """מחזיר סטטוס מפורט של כל מערכות הגיבוי"""
        try:
            status = {
                "local_backup_dir": os.path.exists(self.local_backup.backup_dir),
                "cloud_backup_configured": bool(BACKUP_DB_URL),
                "s3_configured": self.s3_backup.is_configured(),
                "onedrive_available": os.path.exists(self.dual_backup.onedrive_path),
                "scheduler_running": self.scheduler.is_running,
                "last_backup_time": None
            }
            
            # בדיקת זמן גיבוי אחרון
            if os.path.exists(self.local_backup.backup_dir):
                backup_files = [f for f in os.listdir(self.local_backup.backup_dir) if f.endswith('.json')]
                if backup_files:
                    latest_file = max(backup_files, key=lambda x: os.path.getmtime(os.path.join(self.local_backup.backup_dir, x)))
                    status["last_backup_time"] = datetime.fromtimestamp(
                        os.path.getmtime(os.path.join(self.local_backup.backup_dir, latest_file))
                    ).isoformat()
            
            return status
            
        except Exception as e:
            logger.error(f"❌ שגיאה בקבלת סטטוס גיבוי: {e}")
            return {}


# 🎯 פונקציות נוחות לשימוש מהירוהשתמש
def run_daily_backup() -> bool:
    """פונקציה נוחה לגיבוי יומי"""
    manager = BackupManager()
    return manager.local_backup.run_backup() is not None

def run_cloud_backup() -> bool:
    """פונקציה נוחה לגיבוי ענן"""
    manager = BackupManager()
    return manager.cloud_backup.run_backup()

def run_full_backup() -> bool:
    """פונקציה נוחה לגיבוי מלא"""
    manager = BackupManager()
    return manager.run_all_backups()

def comprehensive_restore() -> bool:
    """פונקציה נוחה לשחזור מקיף"""
    manager = BackupManager()
    return manager.restore_manager.comprehensive_restore()

def start_backup_scheduler() -> bool:
    """פונקציה נוחה להפעלת מתזמן"""
    manager = BackupManager()
    return manager.scheduler.start_scheduler()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("🔒 מערכת גיבוי מאוחדת")
        print("========================")
        print("שימוש: python backup_system.py [command] [options]")
        print()
        print("פקודות זמינות:")
        print("  backup          - גיבוי יומי מקומי")
        print("  cloud           - גיבוי ענן")
        print("  internal        - גיבוי פנימי")
        print("  s3              - גיבוי AWS S3")
        print("  dual            - גיבוי כפול")
        print("  full            - גיבוי מלא (כל הסוגים)")
        print("  restore         - שחזור מקיף")
        print("  schedule start  - הפעלת מתזמן")
        print("  schedule stop   - עצירת מתזמן")
        print("  status          - סטטוס מערכת")
        print("  cleanup         - ניקוי גיבויים ישנים")
        sys.exit(1)
    
    command = sys.argv[1]
    manager = BackupManager()
    
    if command == "backup":
        success = manager.local_backup.run_backup()
        print("✅ גיבוי הושלם" if success else "❌ גיבוי נכשל")
    
    elif command == "cloud":
        success = manager.cloud_backup.run_backup()
        print("✅ גיבוי ענן הושלם" if success else "❌ גיבוי ענן נכשל")
    
    elif command == "internal":
        success = manager.internal_backup.run_backup()
        print("✅ גיבוי פנימי הושלם" if success else "❌ גיבוי פנימי נכשל")
    
    elif command == "s3":
        success = manager.s3_backup.run_backup()
        print("✅ גיבוי S3 הושלם" if success else "❌ גיבוי S3 נכשל")
    
    elif command == "dual":
        success = manager.dual_backup.run_backup()
        print("✅ גיבוי כפול הושלם" if success else "❌ גיבוי כפול נכשל")
    
    elif command == "full":
        success = manager.run_all_backups()
        print("✅ גיבוי מלא הושלם" if success else "❌ גיבוי מלא נכשל")
    
    elif command == "restore":
        success = manager.restore_manager.comprehensive_restore()
        print("✅ שחזור הושלם" if success else "❌ שחזור נכשל")
    
    elif command == "schedule":
        if len(sys.argv) > 2:
            if sys.argv[2] == "start":
                success = manager.scheduler.start_scheduler()
                print("✅ מתזמן הופעל" if success else "❌ הפעלת מתזמן נכשלה")
            elif sys.argv[2] == "stop":
                manager.scheduler.stop_scheduler()
                print("✅ מתזמן נעצר")
        else:
            print("שימוש: python backup_system.py schedule [start|stop]")
    
    elif command == "status":
        status = manager.get_backup_status()
        print("📊 סטטוס מערכת הגיבוי:")
        print("=" * 30)
        for key, value in status.items():
            icon = "✅" if value else "❌"
            print(f"{icon} {key}: {value}")
    
    elif command == "cleanup":
        manager.cleanup_old_backups()
        print("✅ ניקוי הושלם")
    
    else:
        print(f"❌ פקודה לא מוכרת: {command}")
        sys.exit(1) 