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
from bot_setup import setup_bot
from message_handler import handle_message
import os
import requests
from gpt_c_logger import clear_gpt_c_html_log
from config import DATA_DIR, PRODUCTION_PORT

# 🔧 תיקון: מניעת setup מרובה
_bot_setup_completed = False
_app_instance = None

def get_bot_app():
    """מחזיר את הapp של הבוט, מגדיר אותו רק פעם אחת"""
    global _bot_setup_completed, _app_instance
    
    # 🔧 תיקון: בדיקה משופרת למניעת setup כפול
    if _bot_setup_completed and _app_instance is not None:
        print("ℹ️  הבוט כבר הוגדר, מחזיר instance קיים")
        return _app_instance
    
    # בדיקה נוספת: אם זה בsandbox mode או עם uvicorn (אבל לא בסביבת production)
    is_sandbox_mode = any(arg in sys.argv[0].lower() for arg in ["sandbox"]) or os.getenv("UVICORN_MODE")
    # בדיקה משופרת לזיהוי סביבת production - בודק גם PORT וגם RENDER
    is_production = os.getenv("RENDER") or os.getenv("PORT") or os.getenv("RAILWAY_STATIC_URL")
    is_local_uvicorn = any(arg in sys.argv[0].lower() for arg in ["uvicorn"]) and not is_production
    
    if is_sandbox_mode or is_local_uvicorn:
        print("⚠️  זוהה sandbox/uvicorn mode - עובד בסביבת פיתוח")
        # המשיכים כרגיל - אין צורך לעצור את הבוט
    
    # בדיקה נוספת: אם זה deploy חדש ברנדר
    if os.getenv("RENDER") and os.getenv("IS_PULL_REQUEST"):
        print("ℹ️  זוהה deploy חדש ברנדר - ממתין להשלמת deployment...")
        time.sleep(5)  # ממתין קצת שהdeployment יסתיים
    
    if not _bot_setup_completed:
        print("🚀 מבצע setup ראשוני של הבוט...")
        _app_instance = setup_bot()
        _bot_setup_completed = True
        print("✅ Setup הבוט הושלם!")
    else:
        print("ℹ️  הבוט כבר הוגדר, מדלג על setup")
    
    return _app_instance

class DummyContext:
    def __init__(self, bot_data):
        self.bot_data = bot_data
        self.bot = get_bot_app().bot  # הוספת גישה לבוט

app_fastapi = FastAPI()

# הוספת app_fastapi כדי שיהיה זמין ל-uvicorn
__all__ = ['app_fastapi']

@app_fastapi.post("/webhook")
async def webhook(request: Request):
    """
    נקודת הכניסה של FastAPI לכל הודעה מהטלגרם (webhook).
    קולט עדכון, יוצר Update, ומעביר ל-handle_message.
    """
    try:
        data = await request.json()
        app = get_bot_app()
        update = Update.de_json(data, app.bot)
        context = DummyContext(app.bot_data)
        if update.message:
            await handle_message(update, context)
        else:
            print("קיבלתי עדכון לא מוכר ב-webhook, מתעלם...")
        return {"ok": True}
    except Exception as ex:
        print(f"❌ שגיאה ב-webhook: {ex}")
        return {"error": str(ex)}

@app_fastapi.get("/")
def root():
    """
    בדיקת חיים (health check) לשרת FastAPI.
    """
    return {"status": "ok"}

@app_fastapi.on_event("startup")
async def on_startup():
    """
    פונקציית אתחול שרת — בודקת תקינות, שולחת התראה אם יש בעיה, ומגדירה webhook בטלגרם אם צריך.
    """
    from utils import health_check
    from notifications import send_error_notification
    
    # וודא שהבוט מוגדר
    get_bot_app()
    
    try:
        health = health_check()
        if not all(health.values()):
            send_error_notification(f"[STARTUP] בעיה בבדיקת תקינות: {health}")
    except Exception as e:
        from traceback import format_exc
        send_error_notification(f"[STARTUP] שגיאה בבדיקת תקינות: {e}\n{format_exc()}")
    # --- הגדרת webhook בטלגרם ---
    try:
        from config import TELEGRAM_BOT_TOKEN
        webhook_url = os.getenv("WEBHOOK_URL")
        if webhook_url:
            set_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
            resp = requests.post(set_url, json={"url": webhook_url})
            print(f"[STARTUP] Telegram setWebhook status: {resp.status_code}, resp: {resp.text}")
        else:
            print("[STARTUP] לא הוגדר WEBHOOK_URL - לא מגדיר webhook בטלגרם.")
    except Exception as e:
        print(f"[STARTUP] שגיאה בהגדרת webhook בטלגרם: {e}")

async def main():
    """
    מריץ את הבוט (אתחול והרצה).
    """
    app = get_bot_app()
    await app.initialize()
    await app.start()
    print("✅ הבוט מוכן ורק מחכה להודעות חדשות!")

if __name__ == "__main__":
    import sys
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    import urllib.parse

    class GptCLogHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/data/gpt_c_results.html") or self.path == "/":
                # Serve the HTML file
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(os.path.join(DATA_DIR, "gpt_c_results.html"), "rb") as f:
                    self.wfile.write(f.read())
            else:
                super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.startswith("/data/gpt_c_results.html") or parsed.path == "/":
                qs = urllib.parse.parse_qs(parsed.query)
                if "clear" in qs and qs["clear"] == ["1"]:
                    clear_gpt_c_html_log()
                    self.send_response(204)
                    self.end_headers()
                    return
            self.send_response(404)
            self.end_headers()

    print(f"🤖 בוט רץ בפורט {PRODUCTION_PORT}!")
    port = PRODUCTION_PORT
    print(f"Serving gpt_c log at http://localhost:{port}/data/gpt_c_results.html (or just http://localhost:{port}/)")
    httpd = HTTPServer(("", port), GptCLogHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()
# תודה1
