"""
main.py
-------
קובץ ראשי רזה שמריץ את הבוט כ-webhook (FastAPI).
הרציונל: רק אתחול, חיבור והרצה. כל הלוגיקה נמצאת בקבצים ייעודיים.

*** שים לב: הבוט עובד עם webhook בלבד (ולא polling)! ***
כל שינוי במבנה חייב לשמור על endpoint של FastAPI ל-webhook.

מכיל רק את הזרימה הראשית של הבוט: אתחול, חיבור, והרצה.
כל הלוגיקה נמצאת בקבצים ייעודיים (bot_setup.py, message_handler.py וכו').
אין לשנות לוגיקה כאן — רק לנהל את הזרימה הראשית.
"""

import asyncio
from fastapi import FastAPI, Request
from telegram import Update
from bot_setup import setup_bot
from message_handler import handle_message
import os
import requests

class DummyContext:
    def __init__(self, bot_data):
        self.bot_data = bot_data

app_fastapi = FastAPI()
app = setup_bot()

@app_fastapi.post("/webhook")
async def webhook(request: Request):
    """
    נקודת הכניסה של FastAPI לכל הודעה מהטלגרם (webhook).
    קולט עדכון, יוצר Update, ומעביר ל-handle_message.
    """
    try:
        data = await request.json()
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
    await app.initialize()
    await app.start()
    print("✅ הבוט מוכן ורק מחכה להודעות חדשות!")

if __name__ == "__main__":
    asyncio.run(main())
# תודה1
