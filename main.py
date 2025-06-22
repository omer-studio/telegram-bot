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

================================================================================

main.py
-------
קובץ ראשי רזה שמריץ את הבוט כ-webhook (FastAPI).
הרציונל: רק אתחול, חיבור והרצה. כל הלוגיקה נמצאת בקבצים ייעודיים.

⚠️  חשוב: אל תפעיל ישירות את הקובץ הזה!
   הפעל את הבוט רק דרך sandbox.py

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
    import sys
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    import urllib.parse
    from gpt_e_logger import clear_gpt_e_html_log

    class GptELogHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/data/gpt_e_results.html") or self.path == "/":
                # Serve the HTML file
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                with open(os.path.join("data", "gpt_e_results.html"), "rb") as f:
                    self.wfile.write(f.read())
            else:
                super().do_GET()

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path.startswith("/data/gpt_e_results.html") or parsed.path == "/":
                qs = urllib.parse.parse_qs(parsed.query)
                if "clear" in qs and qs["clear"] == ["1"]:
                    clear_gpt_e_html_log()
                    self.send_response(204)
                    self.end_headers()
                    return
            self.send_response(404)
            self.end_headers()

    port = 8000
    print(f"Serving gpt_c log at http://localhost:{port}/data/gpt_e_results.html (or just http://localhost:{port}/)")
    httpd = HTTPServer(("", port), GptELogHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()
# תודה1
