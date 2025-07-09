#!/usr/bin/env python3
"""
📅 משפט היומי לגיבוי פנימי
מריץ גיבוי כל יום בשעה 01:00 בלילה
"""

import time
import threading
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from internal_backup_system import run_internal_backup, cleanup_old_internal_backups
from simple_logger import logger
from admin_notifications import send_admin_notification

def scheduled_internal_backup():
    """מריץ גיבוי מתוזמן"""
    try:
        logger.info("🏠 מתחיל גיבוי פנימי מתוזמן...")
        
        # גיבוי
        success = run_internal_backup()
        
        if success:
            logger.info("✅ גיבוי פנימי מתוזמן הושלם בהצלחה")
            
            # ניקוי גיבויים ישנים (שמירת 7 ימים)
            cleanup_old_internal_backups(7)
            
        else:
            logger.error("❌ גיבוי פנימי מתוזמן נכשל")
            send_admin_notification(
                "🚨 **גיבוי פנימי יומי נכשל**\n\n" +
                "❌ הגיבוי האוטומטי לא הצליח\n" +
                "🔧 נדרשת בדיקה ידנית",
                urgent=True
            )
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בגיבוי מתוזמן: {e}")
        send_admin_notification(
            f"🚨 **שגיאה בגיבוי יומי**\n\n" +
            f"❌ שגיאה: {e}\n" +
            f"🔧 נדרשת בדיקה ידנית",
            urgent=True
        )

def run_backup_scheduler():
    """מפעיל את המתזמן לגיבוי יומי"""
    try:
        scheduler = BackgroundScheduler()
        
        # תזמון גיבוי יומי ב-01:00
        scheduler.add_job(
            scheduled_internal_backup,
            'cron',
            hour=1,
            minute=0,
            id='daily_internal_backup'
        )
        
        scheduler.start()
        logger.info("📅 מתזמן גיבוי פנימי הופעל - יומי ב-01:00")
        
        # לולאת הפעלה
        try:
            while True:
                time.sleep(3600)  # בדיקה כל שעה
        except KeyboardInterrupt:
            logger.info("⏹️ מתזמן גיבוי פנימי הופסק")
        finally:
            scheduler.shutdown()
            
    except Exception as e:
        logger.error(f"🚨 שגיאה במתזמן גיבוי: {e}")

def run_backup_scheduler_background():
    """מפעיל את המתזמן ברקע"""
    try:
        scheduler = BackgroundScheduler()
        
        # תזמון גיבוי יומי ב-01:00
        scheduler.add_job(
            scheduled_internal_backup,
            'cron',
            hour=1,
            minute=0,
            id='daily_internal_backup'
        )
        
        scheduler.start()
        logger.info("🎯 מתזמן גיבוי פנימי הופעל ברקע - יומי ב-01:00")
        return scheduler
        
    except Exception as e:
        logger.error(f"🚨 שגיאה בהפעלת מתזמן ברקע: {e}")
        return None

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "background":
        run_backup_scheduler_background()
        # שמירה על התוכנית חיה
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("⏹️ הפעלת מתזמן ברקע הופסקה")
    else:
        run_backup_scheduler() 