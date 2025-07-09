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
    
    # HTTP/API timeouts
    HTTP_REQUEST_TIMEOUT = 15  # שניות לבקשות HTTP כלליות
    HTTP_REQUEST_TIMEOUT_SHORT = 10  # שניות לבקשות HTTP קצרות
    HTTP_REQUEST_TIMEOUT_LONG = 30  # שניות לבקשות HTTP ארוכות
    
    # Database timeouts
    DATABASE_QUERY_TIMEOUT = 5  # שניות לשאילתות DB
    DATABASE_CONNECTION_TIMEOUT = 10  # שניות לחיבור DB
    DATABASE_QUEUE_TIMEOUT = 1  # שניות לqueue של metrics
    DATABASE_QUEUE_TIMEOUT_MICRO = 0.001  # מילישניות לqueue מהיר
    
    # GPT timeouts
    GPT_PROCESSING_TIMEOUT = 120  # שניות לעיבוד GPT
    
    # Subprocess timeouts
    SUBPROCESS_TIMEOUT = 60  # שניות לפעולות subprocess כלליות
    SUBPROCESS_TIMEOUT_SHORT = 5  # שניות לפעולות subprocess קצרות
    SUBPROCESS_TIMEOUT_MEDIUM = 30  # שניות לפעולות subprocess בינוניות
    
    # SSH/Remote timeouts
    SSH_CONNECTION_TIMEOUT = 10  # שניות לחיבור SSH
    SSH_COMMAND_TIMEOUT = 15  # שניות לביצוע פקודת SSH
    
    # Authentication timeouts
    AUTH_SESSION_TIMEOUT = 60  # שניות לסשן אימות
    AUTH_TOKEN_TIMEOUT = 300  # שניות לטוקן אימות
    
    # Concurrent session timeouts
    CONCURRENT_SESSION_TIMEOUT = 50.0  # שניות (50 שניות - תוקן מ-300!)
    CONCURRENT_CLEANUP_INTERVAL = 30  # שניות בין ניקוי סשנים
    
    # Queue/Worker timeouts
    WORKER_QUEUE_TIMEOUT = 1  # שניות לqueue עובדים
    WORKER_THREAD_JOIN_TIMEOUT = 5  # שניות להצטרפות thread
    
    # Logging timeouts
    LOG_QUEUE_TIMEOUT = 1  # שניות לqueue לוגים
    LOG_FLUSH_TIMEOUT = 2  # שניות לשטיפת לוגים
    
    # Message delays
    TEMP_MESSAGE_DELAY = 3  # שניות עד הודעת ביניים
    
    # Render API timeouts
    RENDER_API_TIMEOUT = 10  # שניות ל-API של Render
    RENDER_LOGS_TIMEOUT = 30  # שניות לקבלת לוגים מ-Render
    
    # Progressive communication
    PROGRESSIVE_COMMUNICATION = ProgressiveCommunication() 