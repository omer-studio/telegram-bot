#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
סקריפט זמני לבדיקת שליחת הודעה עם פורמט HTML החדש
"""

import asyncio
import sys
import os

# הוספת הנתיב לשורש הפרויקט
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import TELEGRAM_BOT_TOKEN
from telegram import Bot

async def send_test_message():
    """שולח הודעת בדיקה עם הפורמט החדש"""
    try:
        # טעינת הטוקן
        bot_token = TELEGRAM_BOT_TOKEN
        if not bot_token:
            print("❌ לא נמצא טוקן בוט")
            return
        
        # יצירת בוט
        bot = Bot(token=bot_token)
        
        # הודעת הבדיקה עם הפורמט החדש (HTML)
        test_message = """
🔧 <b>בדיקת פורמט חדש!</b> 

היי! זה בדיקה של הפורמט החדש שתיקנו.

עכשיו אתה אמור לראות:
• <b>טקסט מודגש</b> במקום *טקסט מודגש*
• <u>טקסט עם קו תחתון</u> במקום _טקסט עם קו תחתון_

✅ אם אתה רואה את הטקסט <b>מעוצב נכון</b> ולא רואה סמלים כמו * או _ - אז <u>התיקון עבד!</u>

🎯 תשלח לי "עבד" אם הכל נראה תקין!
        """.strip()
        
        # בקשת chat_id מהמשתמש
        chat_id = input("🔍 הכנס את ה-chat_id שלך (או לחץ Enter לעזרה): ").strip()
        
        if not chat_id:
            print("""
📱 איך לקבל את ה-chat_id שלך:

1. שלח הודעה ל: @userinfobot
2. הוא יחזיר לך את המזהה שלך
3. או בדוק בלוגים של הבוט את ההודעות האחרונות

לחלופין, שלח הודעה כלשהי לבוט ובדוק את הלוגים.
            """)
            return
        
        # שליחת ההודעה
        print(f"📤 שולח הודעת בדיקה לטלגרם...")
        print(f"🎯 Chat ID: {chat_id}")
        print(f"📝 תוכן ההודעה:\n{test_message}")
        print("-" * 50)
        
        await bot.send_message(
            chat_id=chat_id,
            text=test_message,
            parse_mode="HTML"
        )
        
        print("✅ הודעת בדיקה נשלחה בהצלחה!")
        print("🔍 בדוק את הטלגרם שלך ותראה איך הפורמט נראה")
        
    except Exception as e:
        print(f"❌ שגיאה בשליחת הודעת בדיקה: {e}")
        print("💡 וודא שה-chat_id נכון ושהבוט יכול לשלוח לך הודעות")

if __name__ == "__main__":
    asyncio.run(send_test_message()) 