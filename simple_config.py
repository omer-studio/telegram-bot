"""
simple_config.py
================
קובץ תצורה פשוט לניהול timeouts ותכונות זמן
נוצר כדי לפתור תלות חסרה במערכת
"""

# ייבוא התצורה הקיימת
from config import config as base_config

# שימוש חוזר בתצורה הקיימת
config = base_config

class ProgressiveCommunication:
    """מחלקה לניהול הודעות progressive בזמן המתנה"""
    
    PROGRESSIVE_MESSAGES = {
        5: "🤔 עוד רגע...",
        10: "⏳ מעבד את בקשתך...", 
        20: "🧠 חושב קשה על התשובה הטובה ביותר...",
        30: "⚡ כמעט מוכן...",
        45: "🔍 מחפש את התשובה המושלמת...",
        60: "🎯 מכין תשובה מפורטת..."
    }
    
    EMERGENCY_MESSAGES = {
        90: "⚠️ לוקח יותר זמן מהרגיל...",
        120: "🚨 יש עיכוב טכני, אנא המתן...",
        180: "💔 משהו השתבש, אנא נסה שוב"
    }
    
    @classmethod
    def get_progressive_message(cls, elapsed_seconds):
        """מחזיר הודעה מתאימה לפי זמן שעבר"""
        all_messages = {**cls.PROGRESSIVE_MESSAGES, **cls.EMERGENCY_MESSAGES}
        
        # מוצא את ההודעה המתאימה לזמן שעבר
        applicable_times = [t for t in all_messages.keys() if t <= elapsed_seconds]
        if applicable_times:
            latest_time = max(applicable_times)
            return all_messages[latest_time]
        
        return "🤔 עוד רגע..."

class TimeoutConfig:
    """מחלקה לניהול כל הזמנים וtimeouts במערכת"""
    
    # Telegram timeouts
    TELEGRAM_SEND_TIMEOUT = 10  # שניות לשליחת הודעה
    TELEGRAM_API_TIMEOUT_PROGRESSIVE = [5, 10, 15, 20, 25]  # Progressive timeouts
    
    # HTTP timeouts
    HTTP_REQUEST_TIMEOUT = 15  # שניות לבקשות HTTP
    
    # GPT timeouts
    GPT_PROCESSING_TIMEOUT = 120  # שניות לעיבוד GPT
    
    # Concurrent session timeouts
    CONCURRENT_SESSION_TIMEOUT = 300.0  # שניות (5 דקות)
    CONCURRENT_CLEANUP_INTERVAL = 30  # שניות בין ניקוי סשנים
    
    # Subprocess timeouts
    SUBPROCESS_TIMEOUT = 60  # שניות לפעולות subprocess
    SUBPROCESS_TIMEOUT_SHORT = 30  # שניות לפעולות קצרות
    
    # Message delays
    TEMP_MESSAGE_DELAY = 3  # שניות עד הודעת ביניים
    
    # Progressive communication
    PROGRESSIVE_COMMUNICATION = ProgressiveCommunication() 