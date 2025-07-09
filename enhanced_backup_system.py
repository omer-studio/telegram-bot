#!/usr/bin/env python3
"""
🚀 מערכת גיבוי מתקדמת - משלבת מספר אסטרטגיות
"""

import os
import shutil
from datetime import datetime
from daily_backup import run_daily_backup
from simple_logger import logger
from admin_notifications import send_admin_notification

def run_enhanced_backup():
    """מריץ גיבוי משולב לכמה מיקומים"""
    try:
        logger.info("🚀 מתחיל גיבוי משולב")
        
        # 1. גיבוי רגיל (לוקלי + Dropbox)
        local_success = run_daily_backup()
        
        backup_results = {
            "local_dropbox": local_success,
            "cloud_db": False,
            "aws_s3": False,
            "google_drive": False
        }
        
        # 2. גיבוי למסד ענן (אם מוגדר)
        if os.getenv("BACKUP_DATABASE_URL"):
            try:
                from cloud_backup import run_cloud_backup
                backup_results["cloud_db"] = run_cloud_backup()
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי מסד ענן: {e}")
        
        # 3. גיבוי ל-AWS S3 (אם מוגדר)
        if os.getenv("AWS_ACCESS_KEY_ID"):
            try:
                from aws_s3_backup import backup_to_s3
                backup_results["aws_s3"] = backup_to_s3()
            except Exception as e:
                logger.error(f"❌ שגיאה בגיבוי S3: {e}")
        
        # 4. גיבוי ל-Google Drive (פשוט - העתקה)
        try:
            backup_results["google_drive"] = copy_to_google_drive()
        except Exception as e:
            logger.error(f"❌ שגיאה בגיבוי Google Drive: {e}")
        
        # סיכום התוצאות
        successful_backups = sum(backup_results.values())
        total_backups = len([k for k in backup_results.keys() if backup_results[k] or os.getenv(get_env_var(k))])
        
        logger.info(f"🎯 גיבוי הושלם: {successful_backups}/{total_backups} מיקומים")
        
        # התראה לאדמין
        status_icons = {True: "✅", False: "❌"}
        message = f"🚀 **גיבוי משולב הושלם**\n\n"
        
        for backup_type, success in backup_results.items():
            if success or os.getenv(get_env_var(backup_type)):
                icon = status_icons[success]
                friendly_name = get_friendly_name(backup_type)
                message += f"{icon} **{friendly_name}**\n"
        
        message += f"\n📊 **הצלחה:** {successful_backups}/{total_backups} מיקומים"
        
        if successful_backups == 0:
            message += "\n🚨 **אזהרה:** כל הגיבויים נכשלו!"
        elif successful_backups < total_backups:
            message += "\n⚠️ **אזהרה:** חלק מהגיבויים נכשלו"
        
        send_admin_notification(message, urgent=(successful_backups == 0))
        
        return successful_backups > 0
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי משולב: {e}")
        return False

def get_env_var(backup_type):
    """מחזיר את משתנה הסביבה לכל סוג גיבוי"""
    env_vars = {
        "local_dropbox": None,  # תמיד זמין
        "cloud_db": "BACKUP_DATABASE_URL",
        "aws_s3": "AWS_ACCESS_KEY_ID",
        "google_drive": "GOOGLE_DRIVE_PATH"
    }
    return env_vars.get(backup_type)

def get_friendly_name(backup_type):
    """מחזיר שם ידידותי לכל סוג גיבוי"""
    names = {
        "local_dropbox": "Dropbox (לוקלי)",
        "cloud_db": "מסד נתונים ענן",
        "aws_s3": "AWS S3",
        "google_drive": "Google Drive"
    }
    return names.get(backup_type, backup_type)

def copy_to_google_drive():
    """מעתיק גיבויים ל-Google Drive (אם זמין)"""
    try:
        google_drive_path = os.getenv("GOOGLE_DRIVE_PATH")
        if not google_drive_path:
            return False
        
        source_dir = "backups/daily_db_backups"
        backup_date = datetime.now().strftime("%Y%m%d")
        target_dir = os.path.join(google_drive_path, "TelegramBot_Backups", backup_date)
        
        # יצירת תיקיית יעד
        os.makedirs(target_dir, exist_ok=True)
        
        # העתקת קבצים
        copied_files = 0
        for filename in os.listdir(source_dir):
            if filename.endswith('.json'):
                source_file = os.path.join(source_dir, filename)
                target_file = os.path.join(target_dir, filename)
                shutil.copy2(source_file, target_file)
                copied_files += 1
        
        logger.info(f"💾 גיבוי Google Drive: {copied_files} קבצים")
        return copied_files > 0
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי Google Drive: {e}")
        return False

if __name__ == "__main__":
    run_enhanced_backup() 