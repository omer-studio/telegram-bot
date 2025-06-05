"""
main.py — קובץ ראשי רזה

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

class DummyContext:
    def __init__(self, bot_data):
        self.bot_data = bot_data

app_fastapi = FastAPI()
app = setup_bot()

@app_fastapi.post("/webhook")
async def webhook(request: Request):
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
    return {"status": "ok"}

async def main():
    await app.initialize()
    await app.start()
    print("✅ הבוט מוכן ורק מחכה להודעות חדשות!")

if __name__ == "__main__":
    asyncio.run(main())
