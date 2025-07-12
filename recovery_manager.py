"""
recovery_manager.py
==================
🎯 מודול מרכזי לניהול התאוששות והודעות אחרונות

עקרונות עיצוב:
✅ כל הלוגיקה במקום אחד
✅ שימוש בשדות user_profiles בלבד
✅ קוד פשוט ובהיר
✅ אין כפילויות

שדות בטבלת user_profiles:
- needs_recovery_message: האם צריך הודעת התאוששות
- recovery_original_message: ההודעה המקורית שהמשתמש שלח לפני הבעיה
- recovery_error_timestamp: מתי הבעיה הטכנית קרתה
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Optional

# ייבוא ברזי ויציב - ללא תלות ב-telegram package
import requests

from utils import get_israel_time, safe_str
from simple_logger import logger
from config import BOT_TOKEN  
from simple_config import TimeoutConfig


class RecoveryManager:
    """מנהל התאוששות מרכזי - כל הפונקציונליות במקום אחד"""
    
    def __init__(self):
        self.bot_token = BOT_TOKEN
        self.telegram_api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    def add_user_to_recovery_list(self, chat_id: str, error_message: str, original_message: str = None) -> bool:
        """
        מוסיף משתמש לרשימת התאוששות
        
        Args:
            chat_id: מזהה המשתמש
            error_message: תיאור השגיאה
            original_message: ההודעה המקורית (אם יש)
        
        Returns:
            bool: האם הפעולה הצליחה
        """
        try:
            from profile_utils import update_user_profile
            
            # עדכון הפרופיל במסד נתונים
            update_data = {
                "needs_recovery_message": True,
                "recovery_error_timestamp": get_israel_time().isoformat()
            }
            
            # 💾 שמירת ההודעה המקורית אם קיימת
            if original_message and original_message.strip():
                update_data["recovery_original_message"] = original_message.strip()
                logger.info(f"🔄 נשמרה הודעה מקורית למשתמש {safe_str(chat_id)}: '{original_message[:50]}...'")
            
            # עדכון במסד נתונים
            success = update_user_profile(safe_str(chat_id), update_data)
            
            if success:
                logger.info(f"✅ משתמש {safe_str(chat_id)} נוסף לרשימת התאוששות")
                return True
            else:
                logger.error(f"❌ נכשל בעדכון פרופיל למשתמש {safe_str(chat_id)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ שגיאה בהוספת משתמש {safe_str(chat_id)} לרשימת התאוששות: {e}")
            return False
    
    def get_users_needing_recovery(self) -> List[Dict]:
        """
        מחזיר רשימת משתמשים שצריכים הודעת התאוששות
        
        Returns:
            List[Dict]: רשימת משתמשים
        """
        try:
            from profile_utils import get_all_users_with_condition
            
            users = get_all_users_with_condition("needs_recovery_message = TRUE")
            
            if not users:
                logger.info("ℹ️ אין משתמשים שצריכים הודעת התאוששות")
                return []
            
            logger.info(f"✅ נמצאו {len(users)} משתמשים שצריכים הודעת התאוששות")
            return users
            
        except Exception as e:
            logger.error(f"❌ שגיאה בטעינת משתמשים לרשימת התאוששות: {e}")
            return []
    
    def mark_user_as_recovered(self, chat_id: str) -> bool:
        """
        מסמן משתמש כמי שהתאושש
        
        Args:
            chat_id: מזהה המשתמש
        
        Returns:
            bool: האם הפעולה הצליחה
        """
        try:
            from profile_utils import update_user_profile
            
            update_data = {
                "needs_recovery_message": False,
                "recovery_original_message": None,
                "recovery_error_timestamp": None
            }
            
            success = update_user_profile(safe_str(chat_id), update_data)
            
            if success:
                logger.info(f"✅ משתמש {safe_str(chat_id)} סומן כמי שהתאושש")
                return True
            else:
                logger.error(f"❌ נכשל בסימון משתמש {safe_str(chat_id)} כמי שהתאושש")
                return False
                
        except Exception as e:
            logger.error(f"❌ שגיאה בסימון משתמש {safe_str(chat_id)} כמי שהתאושש: {e}")
            return False
    
    async def send_recovery_message_to_user(self, chat_id: str, original_message: str = None) -> bool:
        """
        שולח הודעת התאוששות למשתמש יחיד
        
        Args:
            chat_id: מזהה המשתמש
            original_message: ההודעה המקורית (אם יש)
        
        Returns:
            bool: האם הפעולה הצליחה
        """
        try:
            # בניית הודעת התאוששות
            if original_message and original_message.strip():
                recovery_message = (
                    "✅ המערכת חזרה לפעול!\n\n"
                    "🔄 עיבדתי את הודעתך שנשלחה קודם:\n"
                    f"💬 \"{original_message[:100]}{'...' if len(original_message) > 100 else ''}\"\n\n"
                    "💡 אשמח אם תשלח שוב את מה שרצית לשאול - עכשיו הכל עובד תקין!\n\n"
                    "🎯 תודה על הסבלנות!"
                )
            else:
                recovery_message = (
                    "✅ המערכת חזרה לפעול!\n\n"
                    "💬 אשמח אם תשלח שוב את מה שרצית לשאול - עכשיו הכל עובד תקין!\n\n"
                    "🎯 תודה על הסבלנות!"
                )
            
            # שליחת ההודעה דרך HTTP API
            payload = {
                "chat_id": safe_str(chat_id),
                "text": recovery_message
            }
            
            response = requests.post(self.telegram_api_url, json=payload, timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                logger.info(f"✅ נשלחה הודעת התאוששות למשתמש {safe_str(chat_id)}")
                return True
            else:
                error_data = response.json() if response.content else {}
                error_desc = error_data.get("description", "Unknown error")
                
                if "chat not found" in error_desc.lower() or "user is deactivated" in error_desc.lower():
                    logger.warning(f"⚠️ משתמש {safe_str(chat_id)} חסום/לא קיים")
                    return False
                else:
                    logger.error(f"❌ שגיאת Telegram למשתמש {safe_str(chat_id)}: {error_desc}")
                    return False
                
        except Exception as e:
            logger.error(f"❌ שגיאה בשליחת הודעת התאוששות למשתמש {safe_str(chat_id)}: {e}")
            return False
    
    async def send_recovery_messages_to_all_users(self) -> Dict[str, int]:
        """
        שולח הודעות התאוששות לכל המשתמשים שצריכים
        
        Returns:
            Dict[str, int]: סטטיסטיקות השליחה
        """
        stats = {"sent": 0, "failed": 0, "skipped": 0}
        
        try:
            users = self.get_users_needing_recovery()
            
            if not users:
                logger.info("ℹ️ אין משתמשים ברשימת ההתאוששות")
                return stats
            
            logger.info(f"🔄 מתחיל שליחת הודעות התאוששות ל-{len(users)} משתמשים...")
            
            for user in users:
                chat_id = user.get('chat_id')
                if not chat_id:
                    stats["skipped"] += 1
                    continue
                
                original_message = user.get('recovery_original_message', '')
                
                # שליחת הודעת התאוששות
                if await self.send_recovery_message_to_user(chat_id, original_message):
                    # סימון המשתמש כמי שהתאושש
                    if self.mark_user_as_recovered(chat_id):
                        stats["sent"] += 1
                    else:
                        stats["failed"] += 1
                else:
                    stats["failed"] += 1
                
                # המתנה קצרה בין הודעות
                await asyncio.sleep(0.5)
            
            logger.info(f"✅ הושלמה שליחת הודעות התאוששות - נשלחו: {stats['sent']}, נכשלו: {stats['failed']}, דולגו: {stats['skipped']}")
            
            # שליחת דיווח לאדמין
            await self._send_admin_recovery_report(stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ שגיאה כללית בשליחת הודעות התאוששות: {e}")
            return stats
    
    async def _send_admin_recovery_report(self, stats: Dict[str, int]):
        """שולח דיווח לאדמין על תוצאות ההתאוששות"""
        try:
            from admin_notifications import send_admin_notification
            
            total_users = stats["sent"] + stats["failed"] + stats["skipped"]
            
            report = (
                f"📊 **דוח התאוששות הושלם**\n\n"
                f"✅ **נשלחו בהצלחה:** {stats['sent']} משתמשים\n"
                f"❌ **נכשלו:** {stats['failed']} משתמשים\n"
                f"⏭️ **דולגו:** {stats['skipped']} משתמשים\n"
                f"📋 **סה\"כ:** {total_users} משתמשים"
            )
            
            send_admin_notification(report)
            
        except Exception as e:
            logger.error(f"❌ שגיאה בשליחת דיווח התאוששות לאדמין: {e}")
    
    def update_last_message_time(self, chat_id: str) -> bool:
        """
        מעדכן את זמן ההודעה האחרונה למשתמש
        
        Args:
            chat_id: מזהה המשתמש
        
        Returns:
            bool: האם הפעולה הצליחה
        """
        try:
            from profile_utils import update_user_profile
            
            update_data = {
                "last_message_time": get_israel_time().isoformat()
            }
            
            success = update_user_profile(safe_str(chat_id), update_data)
            
            if success:
                logger.debug(f"✅ עודכן זמן הודעה אחרונה למשתמש {safe_str(chat_id)}")
                return True
            else:
                logger.error(f"❌ נכשל בעדכון זמן הודעה אחרונה למשתמש {safe_str(chat_id)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ שגיאה בעדכון זמן הודעה אחרונה למשתמש {safe_str(chat_id)}: {e}")
            return False
    
    def get_last_message_time(self, chat_id: str) -> Optional[str]:
        """
        מחזיר את זמן ההודעה האחרונה של המשתמש
        
        Args:
            chat_id: מזהה המשתמש
        
        Returns:
            Optional[str]: זמן ההודעה האחרונה או None
        """
        try:
            from profile_utils import get_user_profile
            
            profile = get_user_profile(safe_str(chat_id))
            last_message_time = profile.get('last_message_time')
            
            if last_message_time:
                logger.debug(f"✅ נמצא זמן הודעה אחרונה למשתמש {safe_str(chat_id)}: {last_message_time}")
                return last_message_time
            else:
                logger.debug(f"ℹ️ אין זמן הודעה אחרונה למשתמש {safe_str(chat_id)}")
                return None
                
        except Exception as e:
            logger.error(f"❌ שגיאה בשליפת זמן הודעה אחרונה למשתמש {safe_str(chat_id)}: {e}")
            return None


# יצירת instance גלובלי
recovery_manager = RecoveryManager()

# פונקציות נוחות לשימוש חיצוני
def add_user_to_recovery_list(chat_id: str, error_message: str, original_message: str = None) -> bool:
    """פונקציה נוחה להוספת משתמש לרשימת התאוששות"""
    return recovery_manager.add_user_to_recovery_list(chat_id, error_message, original_message)

def get_users_needing_recovery() -> List[Dict]:
    """פונקציה נוחה לקבלת רשימת משתמשים שצריכים התאוששות"""
    return recovery_manager.get_users_needing_recovery()

def mark_user_as_recovered(chat_id: str) -> bool:
    """פונקציה נוחה לסימון משתמש כמי שהתאושש"""
    return recovery_manager.mark_user_as_recovered(chat_id)

async def send_recovery_messages_to_all_users() -> Dict[str, int]:
    """פונקציה נוחה לשליחת הודעות התאוששות לכל המשתמשים"""
    return await recovery_manager.send_recovery_messages_to_all_users()

def update_last_message_time(chat_id: str) -> bool:
    """פונקציה נוחה לעדכון זמן הודעה אחרונה"""
    return recovery_manager.update_last_message_time(chat_id)

def get_last_message_time(chat_id: str) -> Optional[str]:
    """פונקציה נוחה לקבלת זמן הודעה אחרונה"""
    return recovery_manager.get_last_message_time(chat_id) 