#!/usr/bin/env python3
"""
📁 גיבוי כפול פשוט - Dropbox + OneDrive
פתרון אידיאלי למשתמש שלנו
"""

import os
import shutil
from datetime import datetime
from daily_backup import run_daily_backup
from simple_logger import logger
from admin_notifications import send_admin_notification

def run_dual_backup():
    """מריץ גיבוי כפול - Dropbox + OneDrive"""
    try:
        logger.info("📁 מתחיל גיבוי כפול (Dropbox + OneDrive)")
        
        # 1. גיבוי רגיל ל-Dropbox (כמו שיש עכשיו)
        dropbox_success = run_daily_backup()
        
        # 2. העתקה נוספת ל-OneDrive
        onedrive_success = copy_to_onedrive()
        
        # סיכום
        if dropbox_success and onedrive_success:
            status = "🎉 שני הגיבויים הצליחו!"
            logger.info(status)
            
            send_admin_notification(
                f"📁 **גיבוי כפול הושלם**\n\n" +
                f"✅ **Dropbox:** {get_backup_size('dropbox')}\n" +
                f"✅ **OneDrive:** {get_backup_size('onedrive')}\n" +
                f"🔒 **הנתונים מוגנים במיקומים שונים**"
            )
            
        elif dropbox_success:
            logger.warning("⚠️ גיבוי Dropbox הצליח, OneDrive נכשל")
            send_admin_notification(
                f"⚠️ **גיבוי חלקי**\n\n" +
                f"✅ **Dropbox:** בוצע\n" +
                f"❌ **OneDrive:** נכשל\n" +
                f"💡 עדיין יש גיבוי אחד תקין"
            )
            
        elif onedrive_success:
            logger.warning("⚠️ גיבוי OneDrive הצליח, Dropbox נכשל")
            
        else:
            logger.error("❌ שני הגיבויים נכשלו!")
            send_admin_notification(
                f"🚨 **כל הגיבויים נכשלו!**\n\n" +
                f"❌ **Dropbox:** נכשל\n" +
                f"❌ **OneDrive:** נכשל\n" +
                f"🔧 **נדרש טיפול מיידי**",
                urgent=True
            )
        
        return dropbox_success or onedrive_success
        
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי כפול: {e}")
        return False

def copy_to_onedrive():
    """מעתיק את הגיבויים ל-OneDrive"""
    try:
        # נתיבי מקור ויעד
        source_dir = "backups/daily_db_backups"
        onedrive_path = "C:/Users/ASUS/OneDrive"
        backup_date = datetime.now().strftime("%Y%m%d")
        target_dir = os.path.join(onedrive_path, "TelegramBot_Backups", backup_date)
        
        # וידוא שהתיקיות קיימות
        if not os.path.exists(source_dir):
            logger.error("❌ תיקיית גיבוי מקור לא קיימת")
            return False
        
        if not os.path.exists(onedrive_path):
            logger.error("❌ OneDrive לא נמצא")
            return False
        
        # יצירת תיקיית יעד
        os.makedirs(target_dir, exist_ok=True)
        
        # העתקת קבצים
        copied_files = 0
        total_size = 0
        
        for filename in os.listdir(source_dir):
            if filename.endswith('.json'):
                source_file = os.path.join(source_dir, filename)
                target_file = os.path.join(target_dir, filename)
                
                # העתקה
                shutil.copy2(source_file, target_file)
                
                # סטטיסטיקות
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

def get_backup_size(location):
    """מחזיר את גודל הגיבוי במיקום נתון"""
    try:
        if location == "dropbox":
            backup_dir = "backups/daily_db_backups"
        elif location == "onedrive":
            backup_date = datetime.now().strftime("%Y%m%d")
            backup_dir = f"C:/Users/ASUS/OneDrive/TelegramBot_Backups/{backup_date}"
        else:
            return "לא ידוע"
        
        if not os.path.exists(backup_dir):
            return "לא קיים"
        
        total_size = 0
        file_count = 0
        
        for filename in os.listdir(backup_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(backup_dir, filename)
                total_size += os.path.getsize(file_path)
                file_count += 1
        
        size_mb = total_size / 1024 / 1024
        return f"{file_count} קבצים ({size_mb:.2f}MB)"
        
    except Exception as e:
        return f"שגיאה: {e}"

def check_backup_status():
    """בודק את סטטוס הגיבויים"""
    try:
        print("📊 סטטוס גיבויים:")
        print("=" * 50)
        
        # בדיקת Dropbox
        dropbox_status = get_backup_size("dropbox")
        print(f"📦 Dropbox: {dropbox_status}")
        
        # בדיקת OneDrive
        onedrive_status = get_backup_size("onedrive")
        print(f"☁️ OneDrive: {onedrive_status}")
        
        # המלצות
        print("\n💡 המלצות:")
        if "שגיאה" in dropbox_status and "שגיאה" in onedrive_status:
            print("🚨 שני הגיבויים בבעיה - הרץ גיבוי מיידי!")
        elif "שגיאה" in dropbox_status:
            print("⚠️ בעיה ב-Dropbox - תבדוק את החיבור")
        elif "שגיאה" in onedrive_status:
            print("⚠️ בעיה ב-OneDrive - תבדוק את החיבור")
        else:
            print("✅ הגיבויים תקינים!")
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת סטטוס: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        check_backup_status()
    else:
        run_dual_backup() 