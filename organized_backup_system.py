#!/usr/bin/env python3
"""
🚨 מערכת זו מושבתת מטעמי אבטחה! 🚨
==============================================
מערכת גיבוי זו יוצרת קבצים חיצוניים - לא מאובטח!
הגיבוי מתבצע כעת אך ורק במסד הנתונים לאבטחה מקסימלית.

⛔ קובץ זה מושבת ויופנה אוטומטית למערכת הפנימית ⛔
"""

import sys
import os
from simple_logger import logger

def security_warning():
    """אזהרת אבטחה - מערכת זו מושבתת"""
    print("⛔ אזהרת אבטחה: מערכת גיבוי קבצים חיצוניים מושבתת!")
    print("🔒 הגיבוי מתבצע אך ורק במסד נתונים לאבטחה מקסימלית")
    print("🔄 מפנה אוטומטית למערכת הפנימית...")
    
    logger.warning("🚨 ניסיון גישה למערכת גיבוי קבצים חיצוניים - מושבת מטעמי אבטחה")
    
    # הפניה אוטומטית למערכת הפנימית
    try:
        from organized_internal_backup import run_organized_internal_backup
        print("✅ מריץ גיבוי במסד נתונים...")
        return run_organized_internal_backup()
    except Exception as e:
        print(f"❌ שגיאה בהפניה למערכת פנימית: {e}")
        return False

# Override all functions to redirect to internal system
def run_organized_backup():
    """🚨 מופנה למערכת פנימית"""
    return security_warning()

def list_organized_backups():
    """🚨 מופנה למערכת פנימית"""
    print("⛔ רשימת גיבויים זמינה רק במערכת הפנימית")
    try:
        from organized_internal_backup import list_organized_internal_backups
        return list_organized_internal_backups()
    except Exception as e:
        print(f"❌ שגיאה: {e}")

def cleanup_old_organized_backups(days=30):
    """🚨 מופנה למערכת פנימית"""
    print("⛔ ניקוי זמין רק במערכת הפנימית")
    try:
        from organized_internal_backup import cleanup_old_organized_internal_backups
        return cleanup_old_organized_internal_backups(days)
    except Exception as e:
        print(f"❌ שגיאה: {e}")

if __name__ == "__main__":
    print("🚨 מערכת גיבוי קבצים חיצוניים מושבתת מטעמי אבטחה!")
    print("🔒 השתמש ב: python organized_internal_backup.py")
    security_warning()

# Disabled the entire original implementation for security reasons
# All backup is now DATABASE-ONLY as requested by the user 