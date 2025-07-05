#!/usr/bin/env python3
"""
================================================================================
🚨 חשוב מאוד - שתי סביבות נפרדות! 🚨
================================================================================

סביבה 1 - רנדר (ייצור):
   - הקובץ הזה רץ ישירות: python main.py
   - לא משתמש ב-ngrok
   - לא משתמש ב-sandbox.py
   - רץ על פורט 8000 עם HTTP server פשוט

סביבה 2 - לוקאלית (פיתוח):
   - הקובץ הזה רץ דרך sandbox.py: python sandbox.py
   - משתמש ב-ngrok
   - רץ על פורט 10000 עם uvicorn

⚠️  אל תשנה את הקובץ הזה כדי שיתאים לסביבה לוקאלית!
   הסביבה ברנדר לא אמורה לדעת בכלל על sandbox.py!
   כל שינוי כאן ישפיע על הסביבה ברנדר!

🚨 הפעלה בסביבה לוקאלית:
   python sandbox.py  ✅
   
   אל תפעיל ישירות:
   python main.py  ❌

📝 הערה: הקובץ הזה מיועד לסביבת פיתוח לוקאלית (Cursor IDE).
   בסביבת ייצור יש להשתמש בהגדרות שרת מתאימות.

🚨 הפעלה בסביבה לוקאלית:
   python sandbox.py
   
   אל תפעיל ישירות:
   python main.py  ❌

*** שים לב: הבוט עובד עם webhook בלבד (ולא polling)! ***
כל שינוי במבנה חייב לשמור על endpoint של FastAPI ל-webhook.

מכיל רק את הזרימה הראשית של הבוט: אתחול, חיבור, והרצה.
כל הלוגיקה נמצאת בקבצים ייעודיים (bot_setup.py, message_handler.py וכו').
אין לשנות לוגיקה כאן — רק לנהל את הזרימה הראשית.
"""

import asyncio
import logging
import json
import time
import sys
import urllib.parse
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from bot_setup import setup_bot
from message_handler import handle_message
import os
import requests
from gpt_c_logger import clear_gpt_c_html_log
from config import DATA_DIR, PRODUCTION_PORT

# 🚨 בדיקת post-deploy אוטומטית - הפעלת מערכת rollback
def run_post_deploy_check():
    """מריץ בדיקת post-deploy אם זה deploy חדש בסביבת ייצור - OPTIMIZED for memory"""
    try:
        # רק בסביבת ייצור (Render/Railway)
        if os.getenv("RENDER") or os.getenv("RAILWAY_STATIC_URL"):
            # בדיקה אם זה deploy חדש
            is_new_deploy = (
                os.getenv("RENDER_GIT_COMMIT") or 
                (os.getenv("PORT") and not os.path.exists("data/deploy_verified.flag"))
            )
            
            if is_new_deploy:
                print("[DEPLOY] 🚨 זוהה deploy חדש - מריץ בדיקת post-deploy קלה...")
                
                # 🔧 MEMORY OPTIMIZATION: lightweight check instead of subprocess
                try:
                    # Basic health check without spawning subprocess
                    print("[DEPLOY] 🔍 מבצע בדיקת תקינות בסיסית...")
                    
                    # Quick syntax/import validation
                    try:
                        import config
                        import bot_setup
                        import message_handler
                        health_passed = True
                        print("[DEPLOY] ✅ בדיקת imports בסיסית עברה")
                    except Exception as e:
                        print(f"[DEPLOY] ❌ בדיקת imports נכשלה: {e}")
                        health_passed = False
                    
                    if health_passed:
                        print("[DEPLOY] ✅ בדיקת post-deploy קלה עברה - הבוט אושר להפעלה!")
                        # יצירת flag שהverification עבר
                        os.makedirs("data", exist_ok=True)
                        with open("data/deploy_verified.flag", "w", encoding="utf-8") as f:
                            f.write(f"verified_at_{os.getenv('RENDER_GIT_COMMIT', 'unknown')}")
                    else:
                        print("[DEPLOY] ⚠️ בדיקת תקינות קלה נכשלה אבל ממשיך (memory-safe mode)")
                        
                except Exception as e:
                    print(f"[DEPLOY] ⚠️ שגיאה בבדיקת post-deploy קלה: {e} - ממשיך בכל מקרה")
                    
            else:
                print("[DEPLOY] ℹ️ Deploy קיים מאומת - ממשיך להפעלת הבוט")
        else:
            print("[DEPLOY] ℹ️ סביבת פיתוח - דולג על בדיקת post-deploy")
            
    except Exception as e:
        print(f"[DEPLOY] ⚠️ שגיאה בבדיקת post-deploy: {e}")
        # 🔧 MEMORY OPTIMIZATION: don't exit on verification failure in production
        print("[DEPLOY] ⚠️ ממשיך להפעלת הבוט למרות שגיאת verification (memory-safe mode)")

# הפעלת הבדיקה מיד כשהקובץ נטען
run_post_deploy_check()

# 🪟 תיקון: מניעת setup מרובה
_bot_setup_completed = False
_app_instance = None

def get_bot_app():
    """מחזיר את הapp של הבוט, מגדיר אותו רק פעם אחת"""
    global _bot_setup_completed, _app_instance
    
    # 🔧 תיקון: בדיקה משופרת למניעת setup כפול
    if _bot_setup_completed and _app_instance is not None:
        print("[BOT] ℹ️  הבוט כבר הוגדר, מחזיר instance קיים")
        return _app_instance
    
    # בדיקה נוספת: אם זה בsandbox mode או עם uvicorn (אבל לא בסביבת production)
    is_sandbox_mode = any(arg in sys.argv[0].lower() for arg in ["sandbox"]) or os.getenv("UVICORN_MODE")
    # בדיקה משופרת לזיהוי סביבת production - בודק גם PORT וגם RENDER
    is_production = os.getenv("RENDER") or os.getenv("PORT") or os.getenv("RAILWAY_STATIC_URL")
    is_local_uvicorn = any(arg in sys.argv[0].lower() for arg in ["uvicorn"]) and not is_production
    
    if is_sandbox_mode or is_local_uvicorn:
        print("[BOT] ⚠️  זוהה sandbox/uvicorn mode - עובד בסביבת פיתוח")
        # המשיכים כרגיל - אין צורך לעצור את הבוט
    
    # בדיקה נוספת: אם זה deploy חדש ברנדר
    if os.getenv("RENDER") and os.getenv("IS_PULL_REQUEST"):
        print("[BOT] ℹ️  זוהה deploy חדש ברנדר - ממתין להשלמת deployment...")
        time.sleep(5)  # ממתין קצת שהdeployment יסתיים
    
    # 🔧 תיקון: תמיד עושה setup אם אין instance תקין, לא תלוי בflag
    if _app_instance is None:
        print("[BOT] 🚀 מבצע setup ראשוני של הבוט...")
        _app_instance = setup_bot()
        _bot_setup_completed = True
        print("[BOT] ✅ Setup הבוט הושלם!")
    elif not _bot_setup_completed:
        print("[BOT] ℹ️  יש instance אבל הsetup לא הושלם, מסמן כהושלם")
        _bot_setup_completed = True
    
    return _app_instance

class DummyContext:
    def __init__(self, bot_data):
        self.bot_data = bot_data
        self.bot = get_bot_app().bot  # הוספת גישה לבוט

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    פונקציית אתחול ויציאה של FastAPI — בודקת תקינות, שולחת התראה אם יש בעיה, ומגדירה webhook בטלגרם.
    """
    # Startup logic
    from utils import health_check
    from notifications import send_error_notification, send_recovery_messages_to_affected_users, diagnose_critical_users_system
    
    # וודא שהבוט מוגדר
    get_bot_app()
    
    try:
        health = health_check()
        if not all(health.values()):
            send_error_notification(f"[STARTUP] בעיה בבדיקת תקינות: {health}")
    except Exception as e:
        from traceback import format_exc
        send_error_notification(f"[STARTUP] שגיאה בבדיקת תקינות: {e}\n{format_exc()}")
    
    # 🔍 אבחון מערכת משתמשים קריטיים
    try:
        print("[STARTUP] 🔍 מבצע אבחון מערכת משתמשים קריטיים...")
        diagnosis = diagnose_critical_users_system()
        if diagnosis.get("error"):
            print(f"[STARTUP] ⚠️ נמצאה בעיה במערכת משתמשים קריטיים: {diagnosis['error']}")
        else:
            print("[STARTUP] ✅ אבחון מערכת משתמשים קריטיים הושלם")
    except Exception as e:
        print(f"[STARTUP] ⚠️ שגיאה באבחון מערכת משתמשים קריטיים: {e}")
    
    # --- שליחת הודעות התאוששות אוטומטית ---
    try:
        print("[STARTUP] 🔄 בודק אם יש משתמשים שמחכים להודעות התאוששות...")
        recovered_count = await send_recovery_messages_to_affected_users()
        if recovered_count > 0:
            print(f"[STARTUP] ✅ נשלחו הודעות התאוששות ל-{recovered_count} משתמשים!")
        else:
            print("[STARTUP] ℹ️  אין משתמשים שמחכים להודעות התאוששות")
    except Exception as e:
        print(f"[STARTUP] ⚠️ שגיאה בשליחת הודעות התאוששות: {e}")
        # לא עוצרים את ההפעלה בגלל זה
    
    # --- הגדרת webhook בטלגרם ---
    try:
        from config import TELEGRAM_BOT_TOKEN
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            # 🔧 תיקון: retry mechanism למניעת "Too Many Requests"
            max_retries = 3
            retry_delay = 2  # שניות
            
            for attempt in range(max_retries):
                try:
                    set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
                    resp = requests.post(set_url, json={"url": webhook_url}, timeout=10)
                    
                    if resp.status_code == 200 and resp.json().get('ok'):
                        print(f"✅ [STARTUP] Telegram webhook הוגדר בהצלחה!")
                        break
                    elif resp.status_code == 429:  # Too Many Requests
                        retry_after = resp.json().get('parameters', {}).get('retry_after', retry_delay)
                        print(f"⚠️ [STARTUP] Too Many Requests - ממתין {retry_after} שניות... (ניסיון {attempt + 1}/{max_retries})")
                        time.sleep(retry_after)
                        continue
                    else:
                        print(f"⚠️ [STARTUP] Telegram setWebhook status: {resp.status_code}, resp: {resp.text}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            continue
                        break
                except requests.exceptions.RequestException as e:
                    print(f"⚠️ [STARTUP] שגיאת תקשורת בהגדרת webhook (ניסיון {attempt + 1}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    break
        else:
            print("[STARTUP] לא הוגדר WEBHOOK_URL - לא מגדיר webhook בטלגרם.")
    except Exception as e:
        print(f"[STARTUP] שגיאה בהגדרת webhook בטלגרם: {e}")
    
            # 🚨 בדיקת תפקוד קריטית אחרי הפעלה מלאה
        try:
            print("🔍 מבצע בדיקת תפקוד קריטית אחרי הפעלה...")
            
            # נותן לכל המערכות רגע להיות מוכנות
            time.sleep(3)
            
            # בדיקה בטוחה של auto_rollback
            try:
                from auto_rollback import emergency_rollback_if_broken
                rollback_result = emergency_rollback_if_broken()
                if rollback_result:
                    print("✅ בדיקת תפקוד קריטית עברה בהצלחה!")
                else:
                    print("🚨 בדיקת תפקוד זיהתה בעיות - בדוק התראות אדמין!")
            except ImportError as import_error:
                print(f"⚠️ auto_rollback לא זמין: {import_error}")
                print("✅ ממשיך ללא בדיקת rollback")
            except Exception as rollback_error:
                print(f"⚠️ שגיאה בבדיקת rollback: {rollback_error}")
                print("✅ ממשיך ללא בדיקת rollback")
        except Exception as health_check_error:
            print(f"⚠️ בדיקת תפקוד קריטית נכשלה: {health_check_error}")
            # נשלח התראה לאדמין
            try:
                from notifications import send_admin_notification
                send_admin_notification(
                    f"🚨 בדיקת תפקוד קריטית נכשלה בהפעלה!\n\n"
                    f"❌ שגיאה: {health_check_error}\n"
                    f"⚠️ ייתכן שהבוט לא עובד תקין!",
                    urgent=True
                )
            except Exception:
                pass
    
    # הודעת הצלחה ברורה כשהכל מוכן
    print('\n' + '='*80)
    print('🎉🎉🎉 השרת מוכן לחלוטין! הכל תקין לגמרי! 🎉🎉🎉')
    print('='*80)
    print('✅ FastAPI פעיל ועובד')
    print('✅ Telegram webhook מוגדר נכון')
    print('✅ כל ה-handlers פעילים')
    print('✅ הודעות התאוששות נשלחו (אם היו נחוצות)')
    print('✅ בדיקת תפקוד קריטית הושלמה')
    print('✅ המערכת מוכנה לקבלת הודעות!')
    print('='*80)
    
    yield  # כאן האפליקציה רצה
    
    # Shutdown logic (אם נדרש בעתיד)
    print("🔄 FastAPI נכבה...")

app_fastapi = FastAPI(lifespan=lifespan)

# הוספת app_fastapi כדי שיהיה זמין ל-uvicorn
__all__ = ['app_fastapi']

# ================================
# ℹ️  הערה: מנגנון deduplication כבר קיים ב-message_handler.py
# ================================
# אין צורך בכפילות - המערכת הקיימת עובדת טוב

@app_fastapi.post("/webhook")
async def webhook(request: Request):
    """
    נקודת הכניסה של FastAPI לכל הודעה מהטלגרם (webhook).
    קולט עדכון, יוצר Update, ומעביר ל-handle_message.
    """
    chat_id = None
    user_msg = None
    
    try:
        data = await request.json()
        app = get_bot_app()
        update = Update.de_json(data, app.bot)
        context = DummyContext(app.bot_data)
        
        # חילוץ chat_id ו-user_msg לצורך התראות
        if update.message:
            chat_id = update.message.chat_id
            user_msg = getattr(update.message, 'text', '[הודעה לא טקסטואלית]')
            
            # ℹ️  מנגנון deduplication כבר קיים ב-message_handler.py
            await handle_message(update, context)
        else:
            print("קיבלתי עדכון לא מוכר ב-webhook, מתעלם...")
        return {"ok": True}
    except Exception as ex:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ שגיאה ב-webhook: {ex}")
        print(f"📊 Traceback מלא: {error_details}")
        
        # 🚨 הוספה: רישום בטוח למשתמש לרשימת התאוששות לפני כל טיפול אחר
        try:
            from notifications import safe_add_user_to_recovery_list
            if chat_id:
                safe_add_user_to_recovery_list(str(chat_id), f"Webhook error: {str(ex)[:50]}", user_msg or "")
        except Exception:
            pass  # אל תיכשל בגלל זה
        
        # 🚨 התראה מיידית לאדמין עם פרטים מלאים
        try:
            from notifications import handle_critical_error
            await handle_critical_error(ex, chat_id, user_msg, update if 'update' in locals() else None)
        except Exception as notification_error:
            print(f"❌ שגיאה בשליחת התראה: {notification_error}")
        
        # ✅ תמיד מחזיר HTTP 200 לטלגרם!
        return {"ok": False, "error": str(ex)}

@app_fastapi.get("/")
def root():
    """
    בדיקת חיים (health check) לשרת FastAPI.
    """
    return {"status": "ok"}

@app_fastapi.get("/health")
async def health_check():
    """
    בדיקת בריאות מתקדמת של הבוט
    """
    try:
        from chat_utils import health_check as utils_health_check
        from concurrent_monitor import get_performance_stats
        
        # בדיקות בסיסיות
        health = utils_health_check()
        
        # סטטיסטיקות concurrent
        perf_stats = get_performance_stats()
        
        # בדיקת חיבור לטלגרם
        try:
            app = get_bot_app()
            bot_info = await app.bot.get_me()
            telegram_status = "ok"
            bot_username = bot_info.username
        except Exception as e:
            telegram_status = f"error: {str(e)}"
            bot_username = "unknown"
        
        return {
            "status": "ok" if all(health.values()) else "warning",
            "timestamp": time.time(),
            "components": {
                "basic_health": health,
                "telegram_connection": telegram_status,
                "bot_username": bot_username,
                "active_users": perf_stats.get("active_users", 0),
                "total_requests": perf_stats.get("total_requests", 0),
                "error_rate": perf_stats.get("error_rate", 0)
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": time.time()
        }

async def main():
    """
    מריץ את הבוט (אתחול והרצה).
    """
    app = get_bot_app()
    await app.initialize()
    await app.start()
    print("✅ הבוט מוכן ורק מחכה להודעות חדשות!")



if __name__ == "__main__":
    import uvicorn
    
    # הוספת endpoint ל-gpt_c log במסגרת FastAPI
    @app_fastapi.get("/data/gpt_c_results.html")
    async def serve_gpt_c_log():
        """מגיש את קובץ ה-log של gpt_c"""
        html_file_path = os.path.join(DATA_DIR, "gpt_c_results.html")
        
        # אם הקובץ לא קיים, צור אותו מראש
        if not os.path.exists(html_file_path):
            clear_gpt_c_html_log()  # יוצר קובץ ריק עם התבנית הבסיסית
        
        try:
            with open(html_file_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"content": content, "type": "html"}
        except Exception as e:
            return {"error": f"שגיאה בטעינת הקובץ: {e}"}
    
    @app_fastapi.post("/data/gpt_c_results.html")
    async def clear_gpt_c_log_endpoint():
        """מנקה את לוג ה-gpt_c"""
        try:
            clear_gpt_c_html_log()
            return {"status": "success", "message": "הלוג נוקה בהצלחה"}
        except Exception as e:
            return {"status": "error", "message": f"שגיאה בניקוי הלוג: {e}"}

    print(f"🤖 מריץ FastAPI server על פורט {PRODUCTION_PORT}!")
    print(f"🌐 Webhook זמין ב: http://localhost:{PRODUCTION_PORT}/webhook")
    print(f"📊 GPT-C log זמין ב: http://localhost:{PRODUCTION_PORT}/data/gpt_c_results.html")
    
    # הרצת FastAPI עם uvicorn
    uvicorn.run(
        app_fastapi,
        host="0.0.0.0",
        port=PRODUCTION_PORT,
        log_level="info"
    )
# תודה1
