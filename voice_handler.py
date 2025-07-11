R"""
🔧 זמנית מבוטל - voice_handler.py
-----------------------------------

⚠️ כרגע הקובץ מבוטל עקב בעיית זיכרון בסביבת הענן.
הבוט יעבוד רק עם הודעות טקסט עד לפתרון הבעיה.

הקובץ המקורי הכיל קוד לתמלול הודעות קוליות באמצעות Whisper,
אבל הוא גרם לחריגה מזיכרון בסביבת production.

כשהבעיה תיפתר, ניתן יהיה לשחזר את הקוד המקורי.
"""

import logging
from typing import Optional

# הגדרת לוגר
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# instance דמה שלא יגרום לקריסות אם מישהו מנסה לייבא
class DisabledVoiceHandler:
    """placeholder זמני במקום VoiceHandler - לא צורך זיכרון"""
    
    def __init__(self):
        logger.info("VoiceHandler מבוטל זמנית עקב מגבלות זיכרון")
    
    async def transcribe_voice_message(self, update, context):
        """פונקציה דמה שמחזירה None"""
        logger.warning("transcribe_voice_message נקרא אבל מבוטל")
        return None
                
# יצירת instance גלובלי דמה
voice_handler = DisabledVoiceHandler() 