#!/usr/bin/env python3
"""
schedule_internal_backup.py
===========================
מתזמן גיבוי מסודר יומי ב-01:00 📅
🔒 מערכת גיבוי מסודרת במסד נתונים בלבד - אבטחת מידע מושלמת!

Schema: backup/
├── user_profiles_backup_10_07_2025
├── chat_messages_backup_10_07_2025  
├── gpt_calls_log_backup_10_07_2025
├── user_profiles_backup_09_07_2025
├── chat_messages_backup_09_07_2025
└── gpt_calls_log_backup_09_07_2025

🗄️ כל הגיבוי במסד נתונים - מתמשך ב-Render, אבטח לחלוטין!
"""

import os
import threading
import time
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
from simple_logger import logger
from admin_notifications import send_admin_notification

# scheduler instance
scheduler = None
scheduler_thread = None

def run_scheduled_organized_backup():
    """מריץ גיבוי מסודר מתוזמן במסד נתונים בלבד"""
    try:
        logger.info("🕐 מתחיל גיבוי מסודר מתוזמן במסד נתונים...")
        
        # 🔒 ייבוא המערכת הפנימי במסד נתונים - אבטח לחלוטין!
        from organized_internal_backup import run_organized_internal_backup, safe_backup_cleanup
        
        # ניקוי טבלאות ישנות במסד נתונים (30 ימים) - מוגן!
        safe_backup_cleanup(30, force=False)  # רק סימולציה בscheduler - ביטחון מקסימלי!
        
        # הרצת גיבוי מסודר במסד נתונים
        success = run_organized_internal_backup()
        
        if success:
            logger.info("✅ גיבוי מסודר פנימי מתוזמן הושלם בהצלחה")
            # הפונקציה עצמה כבר שולחת הודעה מפורטת עם תצוגה ויזואלית
        else:
            logger.error("❌ גיבוי מסודר פנימי מתוזמן נכשל")
            send_admin_notification("❌ **גיבוי מסודר יומי במסד** נכשל!", urgent=True)
            
    except Exception as e:
        logger.error(f"❌ שגיאה בגיבוי מסודר פנימי מתוזמן: {e}")
        send_admin_notification(f"❌ **שגיאה בגיבוי מסודר יומי:**\n```{e}```", urgent=True)

def start_backup_scheduler():
    """מתחיל את תזמון הגיבוי המסודר"""
    global scheduler, scheduler_thread
    
    try:
        # אם הsrcheduler כבר רץ, עצור אותו
        if scheduler and scheduler.running:
            logger.info("🔄 עוצר scheduler קיים...")
            scheduler.shutdown()
        
        # יצירת scheduler חדש
        scheduler = BackgroundScheduler()
        
        # הוספת משימה יומית ב-01:00
        scheduler.add_job(
            func=run_scheduled_organized_backup,
            trigger=CronTrigger(hour=1, minute=0),  # 01:00 בלילה
            id='organized_backup_job',
            name='Organized Backup Job',
            replace_existing=True
        )
        
        # הפעלת הscheduler
        scheduler.start()
        
        logger.info("🕐 scheduler גיבוי מסודר פנימי הופעל - גיבוי יומי ב-01:00 (מסד נתונים בלבד)")
        
        # רישום פונקציה לסגירה נקייה
        atexit.register(stop_backup_scheduler)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהפעלת scheduler גיבוי מסודר: {e}")
        return False

def stop_backup_scheduler():
    """עוצר את תזמון הגיבוי המסודר"""
    global scheduler
    
    try:
        if scheduler and scheduler.running:
            scheduler.shutdown()
            logger.info("🔻 scheduler גיבוי מסודר הופסק")
        
    except Exception as e:
        logger.error(f"❌ שגיאה בעצירת scheduler גיבוי מסודר: {e}")

def get_scheduler_status():
    """מחזיר מצב הscheduler"""
    try:
        if scheduler and scheduler.running:
            jobs = scheduler.get_jobs()
            return {
                "running": True,
                "jobs_count": len(jobs),
                "next_run": jobs[0].next_run_time if jobs else None
            }
        else:
            return {"running": False}
            
    except Exception as e:
        logger.error(f"❌ שגיאה בבדיקת מצב scheduler: {e}")
        return {"running": False, "error": str(e)}

def is_scheduler_running():
    """בודק אם הscheduler רץ"""
    try:
        return scheduler and scheduler.running
    except:
        return False

def run_backup_now():
    """מריץ גיבוי מסודר מיידי במסד נתונים"""
    try:
        logger.info("🚀 מריץ גיבוי מסודר פנימי מיידי...")
        
        # הרצה בthread נפרד כדי לא לחסום
        backup_thread = threading.Thread(target=run_scheduled_organized_backup)
        backup_thread.daemon = True
        backup_thread.start()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ שגיאה בהרצת גיבוי פנימי מיידי: {e}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "start":
            if start_backup_scheduler():
                print("✅ scheduler הופעל")
                # השארה של הthread חי
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n🔻 עוצר scheduler...")
                    stop_backup_scheduler()
            else:
                print("❌ שגיאה בהפעלת scheduler")
                
        elif command == "stop":
            stop_backup_scheduler()
            print("🔻 scheduler הופסק")
            
        elif command == "status":
            status = get_scheduler_status()
            print(f"🔍 מצב scheduler: {status}")
            
        elif command == "run":
            if run_backup_now():
                print("🚀 גיבוי מסודר התחיל")
            else:
                print("❌ שגיאה בהרצת גיבוי מיידי")
                
        else:
            print("שימוש: python schedule_internal_backup.py [start|stop|status|run]")
    else:
        print("שימוש: python schedule_internal_backup.py [start|stop|status|run]") 