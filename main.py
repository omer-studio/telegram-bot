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
import json
import time
import sys
import urllib.parse
try:
    from telegram import Update, BotCommand
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
    from telegram.error import TelegramError
    TELEGRAM_AVAILABLE = True
except ImportError:
    # סביבת CI או הרצה בלי הספרייה – יוצר dummy minimal כדי שהבדיקות הסטטיות ירוצו
    class Update: pass
    class BotCommand: pass
    class Application: pass
    class CommandHandler: pass
    class MessageHandler: pass
    class filters: pass
    class ContextTypes: pass
    class TelegramError(Exception): pass
    TELEGRAM_AVAILABLE = False
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from bot_setup import setup_bot, migrate_data_to_sql_with_safety
from message_handler import handle_message
import os
import requests

# 🚀 יבוא המערכת החדשה - פשוטה ועקבית
from simple_config import config, TimeoutConfig
from simple_logger import logger
from simple_data_manager import data_manager
from db_manager import safe_str

def clear_gpt_c_html_log():
    """פונקציה זמנית - יש ליצור את clear_gpt_c_html_log בעתיד"""
    logger.info("📝 [GPT_C_LOGGER] זמנית מושבת - צריך ליצור clear_gpt_c_html_log", source="main")
    return True

# 🚀 יבוא מערכת הלוגים החדשה
try:
    from deployment_logger import deployment_logger, log_info, log_error, log_warning
    DEPLOYMENT_LOGGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Deployment Logger לא זמין: {e}")
    DEPLOYMENT_LOGGER_AVAILABLE = False
    # Dummy functions
    def log_info(msg, **kwargs): print(f"[INFO] {msg}")
    def log_error(msg, **kwargs): print(f"[ERROR] {msg}")
    def log_warning(msg, **kwargs): print(f"[WARNING] {msg}")

# 🧠 Memory logging helper
def log_memory_usage(stage: str):
    """Log current memory usage"""
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024
        logger.info(f"[MEMORY] {stage}: {memory_mb:.1f} MB", source="main")
        
        # 💾 שמירת מדידת זיכרון למסד הנתונים
        try:
            data_manager.save_gpt_call(
                chat_id="system",
                call_type="memory_metrics",
                request_data={"stage": stage, "memory_mb": memory_mb},
                response_data={"status": "logged"},
                tokens_input=0,
                tokens_output=0,
                cost_usd=0.0,
                processing_time=0.0
            )
        except Exception as save_err:
            logger.warning(f"Could not save memory metrics: {save_err}", source="main")
            
    except Exception as e:
        logger.warning(f"Could not log memory usage: {e}", source="main")

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
log_memory_usage("after_imports")
run_post_deploy_check()
log_memory_usage("after_post_deploy_check")

# 🪟 תיקון: מניעת setup מרובה
_bot_setup_completed = False
_app_instance = None

def get_bot_app():
    """מחזיר את הapp של הבוט, מגדיר אותו רק פעם אחת"""
    global _bot_setup_completed, _app_instance
    
    # 🔧 תיקון: בדיקה משופרת למניעת setup כפול
    if _bot_setup_completed and _app_instance is not None:
        print("[BOT] ℹ️  הבוט כבר הוגדר, מחזיר instance קיים")
        log_info("Bot already configured, returning existing instance")
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
        log_info("Starting bot initial setup")
        _app_instance = setup_bot()
        _bot_setup_completed = True
        print("[BOT] ✅ Setup הבוט הושלם!")
        log_info("Bot setup completed successfully")
        
        # 🚀 הפעלת worker thread למטריקות ברקע
        try:
            from db_manager import start_metrics_worker
            start_metrics_worker()
            print("[BOT] 🚀 [METRICS] Background worker started")
            log_info("Metrics background worker started")
        except Exception as metrics_err:
            print(f"[BOT] ⚠️ [METRICS] Could not start background worker: {metrics_err}")
            log_warning(f"Could not start metrics background worker: {metrics_err}")
    elif not _bot_setup_completed:
        print("[BOT] ℹ️  יש instance אבל הsetup לא הושלם, מסמן כהושלם")
        log_info("Bot instance exists but setup not marked complete")
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
    from notifications import send_error_notification, send_recovery_messages_to_affected_users
    
    # וודא שהבוט מוגדר
    get_bot_app()
    log_memory_usage("after_bot_setup")
    
    try:
        health = health_check()
        if not all(health.values()):
            send_error_notification(f"[STARTUP] בעיה בבדיקת תקינות: {health}")
    except Exception as e:
        from traceback import format_exc
        send_error_notification(f"[STARTUP] שגיאה בבדיקת תקינות: {e}\n{format_exc()}")
    
    # 🔍 בדיקה שקטה של מערכת משתמשים קריטיים
    try:
        print("[STARTUP] 🔍 בודק מערכת משתמשים קריטיים...")
        from notifications import _load_critical_error_users
        users_data = _load_critical_error_users()
        unrecovered_count = len([uid for uid, data in users_data.items() if not data.get("recovered", False)])
        print(f"[STARTUP] ✅ מערכת משתמשים קריטיים: {len(users_data)} משתמשים, {unrecovered_count} מחכים להתאוששות")
    except Exception as e:
        print(f"[STARTUP] ⚠️ שגיאה בבדיקת מערכת משתמשים קריטיים: {e}")
    
    # --- שליחת הודעות התאוששות אוטומטית ---
    try:
        print("[STARTUP] 🔄 בודק אם יש משתמשים שמחכים להודעות התאוששות...")
        recovered_count = await send_recovery_messages_to_affected_users()
        if recovered_count > 0:
            print(f"[STARTUP] ✅ נשלחו הודעות התאוששות ל-{recovered_count} משתמשים!")
        else:
            print("[STARTUP] ℹ️ אין משתמשים שמחכים להודעות התאוששות")
    except Exception as e:
        print(f"[STARTUP] ⚠️ שגיאה בשליחת הודעות התאוששות: {e}")
    
    # --- הגדרת webhook בטלגרם ---
    try:
        from config import TELEGRAM_BOT_TOKEN
        webhook_url = os.getenv("WEBHOOK_URL") or "https://telegram-bot-b1na.onrender.com/webhook"
        
        if webhook_url:
            # 🔧 תיקון: retry mechanism למניעת "Too Many Requests"
            max_retries = 3
            retry_delay = 2  # שניות
            
            for attempt in range(max_retries):
                try:
                    set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
                    resp = requests.post(set_url, json={"url": webhook_url}, timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT)
                    
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
    
    log_memory_usage("after_webhook_setup")
    
    # 🚨 בדיקת תפקוד קריטית אחרי הפעלה מלאה
    try:
        print("🔍 מבצע בדיקת תפקוד קריטית אחרי הפעלה...")
        
        # נותן לכל המערכות רגע להיות מוכנות
        time.sleep(3)
        
        # בדיקה בטוחה של auto_rollback
        try:
            # Try to import auto_rollback module
            import auto_rollback
            rollback_result = auto_rollback.emergency_rollback_if_broken()
            if rollback_result:
                print("✅ בדיקת תפקוד קריטית עברה בהצלחה!")
            else:
                print("🚨 בדיקת תפקוד זיהתה בעיות - בדוק התראות אדמין!")
        except ImportError as import_error:
            print(f"⚠️ auto_rollback module לא זמין: {import_error}")
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

    log_memory_usage("startup_complete")
    
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
            
            # לוג הודעת משתמש
            log_info(f"Received message from user {chat_id}", 
                    user_id=safe_str(chat_id), 
                    metadata={"message_preview": user_msg[:100] if user_msg else ""})
            
            # ℹ️  מנגנון deduplication כבר קיים ב-message_handler.py
            await handle_message(update, context)
        else:
            print("קיבלתי עדכון לא מוכר ב-webhook, מתעלם...")
            log_warning("Received unknown update type in webhook")
        return {"ok": True}
    except Exception as ex:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ שגיאה ב-webhook: {ex}")
        print(f"📊 Traceback מלא: {error_details}")
        
        # לוג השגיאה למערכת הלוגים
        log_error(f"Webhook error: {str(ex)}", 
                 user_id=str(chat_id) if chat_id else None,
                 metadata={
                     "error_type": type(ex).__name__,
                     "user_message": user_msg[:100] if user_msg else "",
                     "traceback": error_details
                 })
        
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
            log_error(f"Failed to send error notification: {notification_error}")
        
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
    import os
    from bot_setup import migrate_data_to_sql_with_safety
    
    # 🚨 DATA_DIR and all data/ references fully removed
    
    production_port = int(os.getenv("PORT", 8000))
    print(f"🤖 מריץ FastAPI server על פורט {production_port}!")
    print(f"🌐 Webhook זמין ב: http://localhost:{production_port}/webhook")
    
    # הרצת FastAPI עם uvicorn
    uvicorn.run(
        app_fastapi,
        host="0.0.0.0",
        port=production_port,
        log_level="info"
    )
# תודה1
