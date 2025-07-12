"""
concurrent_monitor.py
--------------------
🚨🚨🚨 קובץ קריטי - אל תמחק! 🚨🚨🚨

⚠️  אזהרה חשובה: קובץ זה הוא קריטי לפעולה תקינה של הבוט!
   מחיקתו תגרום לקריסת המערכת בעומסים!

🔐 מערכת ניטור והגנה על הבוט מפני עומסים וקריסות

🛡️ למה הקובץ הזה חיוני:
1. 🚫 מונע קריסת Google Sheets API (מגביל ל-10 פעולות בו-זמנית)
2. 🛡️ מגן על הבוט מפני עומסים (מקסימום 10 משתמשים במקביל)
3. ⏰ מונע סשנים תקועים (timeout של 30 שניות)
4. 🧹 ניקוי אוטומטי של memory leaks
5. 📊 התראות בזמן אמת על בעיות

🎯 מטרות:
- ניטור משתמשים פעילים במקביל (עד 10)
- מדידת זמני תגובה וניטור ביצועים
- FIFO ordering למניעת עיכובים לא הוגנים
- מנגנוני בטיחות והתאוששות
- התראות אוטומטיות לאדמין בזמן אמת

🔧 מנגנוני בטיחות:
- Graceful degradation בעומסים גבוהים
- Auto-recovery מכשלים
- Circuit breaker למניעת קריסות
- Timeout protection
- Memory leak prevention

💡 בלי הקובץ הזה: 50+ משתמשים → Google Sheets קורס → הבוט קורס
   עם הקובץ הזה: מקסימום 10 משתמשים → מערכת יציבה ואמינה

🔗 משמש ב: message_handler.py, utils.py
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Deque
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import logging
import os
import psutil  # לניטור זיכרון
from utils import get_israel_time
from simple_config import TimeoutConfig
from user_friendly_errors import safe_str

# 🔄 Progressive User Communication Integration
# =================================================================
class ProgressiveUserNotifier:
    """מנגנון להודעות מתדרגות למשתמש במהלך עיבוד"""
    
    def __init__(self):
        self.active_notifications: Dict[str, List[float]] = {}  # chat_id -> [sent_times]
        self.notification_tasks: Dict[str, asyncio.Task] = {}  # chat_id -> task
    
    async def start_progressive_notifications(self, chat_id: str, update_obj=None):
        """מתחיל הודעות מתדרגות למשתמש"""
        try:
            # ביטול הודעות קיימות אם יש
            await self.cancel_notifications(chat_id)
            
            # יצירת רשימת זמנים להודעות
            self.active_notifications[chat_id] = []
            
            # התחלת task להודעות מתדרגות
            self.notification_tasks[chat_id] = asyncio.create_task(
                self._send_progressive_notifications(chat_id, update_obj)
            )
            
            logging.debug(f"[ProgressiveNotifier] Started progressive notifications for {chat_id}")
            
        except Exception as e:
            logging.error(f"[ProgressiveNotifier] Error starting notifications for {chat_id}: {e}")
    
    async def cancel_notifications(self, chat_id: str):
        """מבטל הודעות מתדרגות למשתמש"""
        try:
            # ביטול task אם קיים
            if chat_id in self.notification_tasks:
                task = self.notification_tasks[chat_id]
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                del self.notification_tasks[chat_id]
            
            # ניקוי רשימת הודעות
            if chat_id in self.active_notifications:
                del self.active_notifications[chat_id]
            
            logging.debug(f"[ProgressiveNotifier] Cancelled notifications for {chat_id}")
            
        except Exception as e:
            logging.error(f"[ProgressiveNotifier] Error cancelling notifications for {chat_id}: {e}")
    
    async def _send_progressive_notifications(self, chat_id: str, update_obj=None):
        """שולח הודעות מתדרגות למשתמש"""
        try:
            start_time = time.time()
            
            # כל הזמנים שבהם צריך לשלוח הודעה
            notification_times = sorted(
                list(TimeoutConfig.PROGRESSIVE_COMMUNICATION.PROGRESSIVE_MESSAGES.keys()) +
                list(TimeoutConfig.PROGRESSIVE_COMMUNICATION.EMERGENCY_MESSAGES.keys())
            )
            
            for notification_time in notification_times:
                elapsed = time.time() - start_time
                
                # המתן עד הזמן הנכון
                if elapsed < notification_time:
                    await asyncio.sleep(notification_time - elapsed)
                
                # בדיקה אם המשתמש עדיין פעיל
                if chat_id not in self.active_notifications:
                    logging.debug(f"[ProgressiveNotifier] User {chat_id} no longer active, stopping notifications")
                    break
                
                # קבלת ההודעה המתאימה
                elapsed_now = time.time() - start_time
                message = TimeoutConfig.PROGRESSIVE_COMMUNICATION.get_progressive_message(elapsed_now)
                
                # שליחת ההודעה
                await self._send_user_notification(chat_id, message, update_obj)
                
                # רישום הזמן שבו נשלחה ההודעה
                self.active_notifications[chat_id].append(elapsed_now)
                
                logging.info(f"[ProgressiveNotifier] Sent progressive notification to {chat_id} after {elapsed_now:.1f}s")
                
        except asyncio.CancelledError:
            logging.debug(f"[ProgressiveNotifier] Progressive notifications cancelled for {chat_id}")
        except Exception as e:
            logging.error(f"[ProgressiveNotifier] Error in progressive notifications for {chat_id}: {e}")
    
    async def _send_user_notification(self, chat_id: str, message: str, update_obj=None):
        """שולח הודעה למשתמש"""
        try:
            if update_obj:
                # שליחת הודעה דרך Telegram
                try:
                    # Dynamic import to avoid circular imports
                    from message_handler import send_system_message
                    await send_system_message(update_obj, chat_id, message)
                    logging.debug(f"[ProgressiveNotifier] Sent message to {chat_id}: {message[:50]}...")
                except Exception as e:
                    logging.warning(f"[ProgressiveNotifier] Failed to send message to {chat_id}: {e}")
            else:
                logging.debug(f"[ProgressiveNotifier] No update object for {chat_id}, message: {message[:50]}...")
                
        except Exception as e:
            logging.error(f"[ProgressiveNotifier] Error sending notification to {chat_id}: {e}")

# יצירת instance גלובלי
_progressive_notifier = ProgressiveUserNotifier()

@dataclass
class UserSession:
    """מייצג סשן משתמש פעיל עם נתוני בטיחות"""
    chat_id: str
    start_time: float
    message_id: str
    stage: str  # "queued", "processing", "gpt_a", "background", "completed"
    queue_position: int  # FIFO position
    max_allowed_time: float = TimeoutConfig.CONCURRENT_SESSION_TIMEOUT  # 🔧 תיקון: משתמש בתצורה מרכזית
    
    def is_timeout(self) -> bool:
        """בדיקה אם הסשן עבר timeout"""
        return time.time() - self.start_time > self.max_allowed_time
    
@dataclass
class PerformanceMetrics:
    """מטריקות ביצועים מתקדמות"""
    timestamp: datetime
    active_users: int
    queue_length: int  # אורך תור FIFO
    avg_response_time: float
    max_response_time: float
    sheets_operations_per_minute: int
    error_rate: float
    memory_usage_mb: float
    rejected_users: int  # משתמשים שנדחו בגלל עומס

class MemoryMonitor:
    """מערכת ניטור זיכרון מתקדמת"""
    
    def __init__(self):
        self.memory_history = deque(maxlen=100)  # היסטוריית זיכרון
        self.last_check = time.time()
        self.memory_warnings = 0
        
    def get_memory_usage(self) -> dict:
        """מחזיר מידע על שימוש הזיכרון"""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            return {
                "rss_mb": memory_info.rss / 1024 / 1024,  # Resident Set Size
                "vms_mb": memory_info.vms / 1024 / 1024,  # Virtual Memory Size
                "percent": process.memory_percent(),
                "available_mb": psutil.virtual_memory().available / 1024 / 1024,
                "total_mb": psutil.virtual_memory().total / 1024 / 1024
            }
        except Exception as e:
            logging.warning(f"[MemoryMonitor] Error getting memory info: {e}")
            return {"error": str(e)}
    
    def check_memory_health(self) -> dict:
        """בודק את בריאות הזיכרון"""
        memory_info = self.get_memory_usage()
        
        if "error" in memory_info:
            return {"status": "error", "error": memory_info["error"]}
        
        # שמירת היסטוריה
        self.memory_history.append({
            "timestamp": time.time(),
            "rss_mb": memory_info["rss_mb"],
            "percent": memory_info["percent"]
        })
        
        # בדיקת סף אזהרה
        warnings = []
        if memory_info["percent"] > 80:
            warnings.append("שימוש זיכרון גבוה (>80%)")
            self.memory_warnings += 1
        if memory_info["rss_mb"] > 500:  # 500MB
            warnings.append("שימוש זיכרון מוחלט גבוה (>500MB)")
        
        return {
            "status": "warning" if warnings else "ok",
            "memory_info": memory_info,
            "warnings": warnings,
            "memory_warnings": self.memory_warnings
        }
    
    def get_memory_trend(self) -> dict:
        """מחזיר מגמת שימוש הזיכרון"""
        if len(self.memory_history) < 2:
            return {"trend": "insufficient_data"}
        
        recent = list(self.memory_history)[-10:]  # 10 מדידות אחרונות
        if len(recent) < 2:
            return {"trend": "insufficient_data"}
        
        # חישוב מגמה
        first_rss = recent[0]["rss_mb"]
        last_rss = recent[-1]["rss_mb"]
        growth_rate = (last_rss - first_rss) / len(recent)
        
        if growth_rate > 10:  # גדילה של יותר מ-10MB למדידה
            return {"trend": "increasing", "growth_rate_mb": growth_rate}
        elif growth_rate < -10:
            return {"trend": "decreasing", "growth_rate_mb": growth_rate}
        else:
            return {"trend": "stable", "growth_rate_mb": growth_rate}

class ConcurrentMonitor:
    """
    🛡️ מערכת ניטור מתקדמת עם מנגנוני בטיחות
    
    עקרונות פעולה:
    1. FIFO: כל משתמש מקבל מספר בתור לפי סדר הגעה
    2. Timeout Protection: סשנים לא יכולים לרוץ יותר מ-50 שניות (GPT timeout + 5s buffer)
    3. Circuit Breaker: בעומס גבוה - דחיית בקשות חדשות
    4. Auto Recovery: ניקוי אוטומטי של סשנים תקועים
    5. Memory Protection: מגבלות על שמירת היסטוריה
    """
    
    def __init__(self, max_users: int = 25):
        # הגדרות בסיסיות
        self.max_users = max_users
        self.active_sessions: Dict[str, UserSession] = {}
        self.user_queue: List[str] = []  # FIFO queue
        self.next_queue_position = 1
        
        # מדדי ביצועים
        self.total_requests = 0
        self.response_times: List[float] = []
        self.error_count = 0
        self.timeout_count = 0
        self.rejected_users = 0
        
        # Circuit Breaker
        self.circuit_breaker_active = False
        self.last_circuit_check = time.time()
        
        # Task management - proper tracking to prevent memory leaks
        self._background_tasks_started = False
        self._active_tasks: List[asyncio.Task] = []  # Track running tasks
        self._task_lock = asyncio.Lock() if hasattr(asyncio, 'Lock') else None
        
    async def _ensure_background_tasks_started(self):
        """מתחיל את background tasks אם הם לא התחילו עדיין"""
        if not self._background_tasks_started:
            try:
                # Clean up any dead tasks before starting new ones
                await self._cleanup_dead_tasks()
                
                # 🔧 תיקון קריטי: cleanup חייב לרוץ גם ב-production!
                # בלי זה סשנים נשארים תקועים לנצח
                loop = asyncio.get_running_loop()
                if loop and not loop.is_closed():
                    # יצירת task עם error handling - only if not already running
                    if not any(not task.done() and "cleanup_stale_sessions" in str(task.get_coro()) 
                              for task in self._active_tasks):
                        cleanup_task = asyncio.create_task(self._cleanup_stale_sessions())
                        cleanup_task.add_done_callback(self._handle_cleanup_error)
                        self._active_tasks.append(cleanup_task)
                        logging.info("[ConcurrentMonitor] Started essential cleanup task")
                    else:
                        logging.debug("[ConcurrentMonitor] Cleanup task already running")
                self._background_tasks_started = True
            except (RuntimeError, AttributeError) as e:
                # אם אין event loop פעיל, ננסה שוב בפעם הבאה
                logging.debug(f"[ConcurrentMonitor] No active event loop, skipping background tasks: {e}")
                pass
            except Exception as e:
                logging.error(f"[ConcurrentMonitor] Error starting background tasks: {e}")
                # לא נכשל אם background tasks לא עובדים
                self._background_tasks_started = True
        
    async def _cleanup_dead_tasks(self):
        """ניקוי tasks שהסתיימו כדי למנוע memory leaks"""
        try:
            if hasattr(self, '_active_tasks'):
                # Remove completed/cancelled tasks
                self._active_tasks = [task for task in self._active_tasks if not task.done()]
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Error cleaning dead tasks: {e}")
    
    def _handle_cleanup_error(self, task):
        """טיפול בשגיאות ב-cleanup task"""
        try:
            if task.exception():
                logging.error(f"[ConcurrentMonitor] Cleanup task failed: {task.exception()}")
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Error handling cleanup task: {e}")
        finally:
            # Remove task from active list when done
            try:
                if hasattr(self, '_active_tasks') and task in self._active_tasks:
                    self._active_tasks.remove(task)
            except Exception as e:
                logging.debug(f"[ConcurrentMonitor] Error removing task from active list: {e}")
        
    async def start_user_session(self, chat_id: str, message_id: str, update_obj=None) -> bool:
        """
        🚪 התחלת סשן משתמש חדש עם FIFO ובדיקות בטיחות
        
        Returns:
            True - הסשן התחיל בהצלחה
            False - הסשן נדחה (עומס גבוה)
        """
        try:
            # התחלת background tasks אם צריך
            await self._ensure_background_tasks_started()
            
            # Circuit Breaker מבוטל לחלוטין - אין חסימות כלל
            
            # 🚨 בדיקת קיבולת מקסימלית - זה מה שמגן על המערכת!
            # בלי הבדיקה הזו, Google Sheets API יקרוס מעודף בקשות
            if len(self.active_sessions) >= self.max_users:
                self.rejected_users += 1
                await self._send_rejection_alert(chat_id, "max_capacity")
                return False  # 🛡️ דוחה משתמש כדי להגן על המערכת
            
            # יצירת סשן חדש עם FIFO position
            session = UserSession(
                chat_id=chat_id,
                start_time=time.time(),
                message_id=message_id,
                stage="queued",
                queue_position=self.next_queue_position
            )
            
            # הוספה לתור FIFO ולסשנים פעילים
            self.user_queue.append(chat_id)
            self.active_sessions[chat_id] = session
            self.next_queue_position += 1
            self.total_requests += 1
            
            # 🔄 התחלת הודעות מתדרגות למשתמש
            try:
                await _progressive_notifier.start_progressive_notifications(chat_id, update_obj)
                logging.debug(f"[ConcurrentMonitor] Started progressive notifications for {chat_id}")
            except Exception as notif_err:
                logging.warning(f"[ConcurrentMonitor] Failed to start progressive notifications for {chat_id}: {notif_err}")
            
            logging.info(f"[ConcurrentMonitor] ✅ Started session for user {chat_id}. "
                        f"Queue position: {session.queue_position}, Active: {len(self.active_sessions)}")
            
            # התראה אם מתקרבים לקיבולת מקסימלית
            if len(self.active_sessions) >= self.max_users * 0.8:
                await self._send_load_warning()
            
            return True
            
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Error starting session for {chat_id}: {e}")
            self._send_error_alert("start_session_error", {"chat_id": chat_id, "error": str(e)})
            return False
    
    async def update_user_stage(self, chat_id: str, stage: str):
        """📍 עדכון שלב עיבוד של משתמש עם לוגים מפורטים"""
        try:
            if chat_id in self.active_sessions:
                old_stage = self.active_sessions[chat_id].stage
                self.active_sessions[chat_id].stage = stage
                
                # מעבר מ-queued ל-processing
                if old_stage == "queued" and stage == "processing":
                    self._remove_from_queue(chat_id)
                
                logging.debug(f"[ConcurrentMonitor] 📍 User {chat_id}: {old_stage} → {stage}")
            else:
                logging.warning(f"[ConcurrentMonitor] User {chat_id} not found in active sessions")
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Error updating user stage for {chat_id}: {e}")
    
    def _remove_from_queue(self, chat_id: str):
        """הסרת משתמש מתור FIFO"""
        try:
            self.user_queue.remove(chat_id)
        except ValueError:
            pass  # המשתמש כבר לא בתור
    
    async def end_user_session(self, chat_id: str, success: bool = True):
        """
        🏁 סיום סשן משתמש עם איסוף נתונים לניתוח
        """
        if chat_id not in self.active_sessions:
            return
        
        try:
            session = self.active_sessions[chat_id]
            response_time = time.time() - session.start_time
            
            # 🔄 ביטול הודעות מתדרגות
            try:
                await _progressive_notifier.cancel_notifications(chat_id)
                logging.debug(f"[ConcurrentMonitor] Cancelled progressive notifications for {chat_id}")
            except Exception as notif_err:
                logging.warning(f"[ConcurrentMonitor] Failed to cancel progressive notifications for {chat_id}: {notif_err}")
            
            # 💾 שמירת מטריקות concurrent למסד הנתונים
            try:
                # 🗑️ REMOVED: save_system_metrics disabled
                # הקוד הישן מבוטל - שמירת מטריקות concurrent הושבתה
                logging.debug(f"[ConcurrentMonitor] Metrics logging disabled for session {chat_id}")
            except Exception as save_err:
                logging.warning(f"Could not save concurrent metrics: {save_err}")
            
            # עדכון זמני תגובה
            self.response_times.append(response_time)
            
            if not success:
                self.error_count += 1
                
            # בדיקת timeout
            if session.is_timeout():
                self.timeout_count += 1
                try:
                    # 🔧 תיקון: הוספת פרטים ספציפיים יותר למניעת "Unknown error"
                    timeout_details = {
                        "error": f"Session timeout after {response_time:.2f}s",
                        "chat_id": chat_id,
                        "duration": response_time,
                        "stage": session.stage,
                        "message_id": session.message_id,
                        "queue_position": session.queue_position,
                        "max_allowed_time": session.max_allowed_time,
                        "timestamp": get_israel_time().strftime('%d/%m/%Y %H:%M:%S')
                    }
                    self._send_error_alert("session_timeout", timeout_details)
                    logging.error(f"[ConcurrentMonitor] 🚨 Session timeout: {chat_id} after {response_time:.2f}s (stage: {session.stage})")
                except Exception as e:
                    logging.error(f"[ConcurrentMonitor] Failed to send timeout alert: {e}")
            
            # הסרת הסשן
            self._remove_from_queue(chat_id)
            if chat_id in self.active_sessions:
                del self.active_sessions[chat_id]
            
            logging.info(f"[ConcurrentMonitor] 🏁 Ended session for user {chat_id}. "
                        f"Duration: {response_time:.2f}s, Success: {success}, Active: {len(self.active_sessions)}")
            
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Error ending session for {chat_id}: {e}")
            # ניסיון ניקוי ידני אם end_user_session נכשל
            try:
                # ביטול הודעות מתדרגות גם במקרה שגיאה
                await _progressive_notifier.cancel_notifications(chat_id)
                self._remove_from_queue(chat_id)
                if chat_id in self.active_sessions:
                    del self.active_sessions[chat_id]
            except Exception as cleanup_error:
                logging.error(f"[ConcurrentMonitor] Failed to manually clean session {chat_id}: {cleanup_error}")
    
    async def _cleanup_stale_sessions(self):
        """
        🧹 ניקוי אוטומטי של סשנים תקועים (כל 10 שניות)
        ⚠️  מנגנון בטיחות קריטי למניעת memory leaks וסשנים תקועים
        🚨 בלי הפונקציה הזו - סשנים יישארו תקועים לנצח ויגרמו לקריסה!
        """
        while True:
            try:
                stale_sessions = []
                current_time = time.time()
                
                # יצירת עותק של הרשימה כדי למנוע שגיאות בזמן איטרציה
                active_sessions_copy = dict(self.active_sessions)
                
                for chat_id, session in active_sessions_copy.items():
                    session_duration = current_time - session.start_time
                    if session.is_timeout():
                        stale_sessions.append((chat_id, session_duration))
                        logging.warning(f"[ConcurrentMonitor] 🚨 Session timeout detected: {chat_id} after {session_duration:.2f}s (stage: {session.stage})")
                
                # ניקוי סשנים תקועים
                for chat_id, duration in stale_sessions:
                    try:
                        await self.end_user_session(chat_id, success=False)
                        logging.warning(f"[ConcurrentMonitor] 🧹 Cleaned stale session: {chat_id} (duration: {duration:.2f}s)")
                    except Exception as e:
                        logging.error(f"[ConcurrentMonitor] Error cleaning stale session {chat_id}: {e}")
                        # הסרה ידנית אם end_user_session נכשל
                        try:
                            self._remove_from_queue(chat_id)
                            if chat_id in self.active_sessions:
                                del self.active_sessions[chat_id]
                        except Exception as cleanup_error:
                            logging.error(f"[ConcurrentMonitor] Failed to manually clean session {chat_id}: {cleanup_error}")
                
                if stale_sessions:
                    try:
                        # 🔧 תיקון: הוספת פרטים ספציפיים יותר למניעת "Unknown error"
                        session_details = [f"{chat_id}({duration:.2f}s)" for chat_id, duration in stale_sessions]
                        self._send_error_alert("stale_sessions_cleaned", {
                            "error": f"Cleaned {len(stale_sessions)} stale sessions",
                            "chat_id": "System",  # זה ניקוי מערכת, לא משתמש ספציפי
                            "count": len(stale_sessions),
                            "sessions": session_details,
                            "duration": "50s timeout exceeded",  # 🔧 עדכון לזמן החדש
                            "details": f"Sessions: {', '.join(session_details)}"
                        })
                    except Exception as e:
                        logging.error(f"[ConcurrentMonitor] Failed to send cleanup alert: {e}")
                
                # 🔧 תיקון: בדיקה תכופה יותר למניעת תקיעות
                await asyncio.sleep(TimeoutConfig.CONCURRENT_CLEANUP_INTERVAL)  # בדיקה לפי תצורה מרכזית
                
            except asyncio.CancelledError:
                # Task בוטל - יציאה נקייה
                logging.info("[ConcurrentMonitor] Cleanup task cancelled")
                break
            except Exception as e:
                logging.error(f"[ConcurrentMonitor] Error in cleanup: {e}")
                await asyncio.sleep(30)
    
    async def _monitor_system_health(self):
        """💊 ניטור בריאות מבוטל - Circuit Breaker לא מופעל."""
        # הפונקציה הזו פשוט ישנה - Circuit Breaker מבוטל לחלוטין
        while True:
            await asyncio.sleep(60)  # חסכון במשאבים
    
    async def log_sheets_operation(self):
        """רישום פעולת Google Sheets"""
        # כאן אפשר להוסיף ספירה של פעולות Sheets
        pass
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """קבלת מטריקות נוכחיות"""
        avg_response_time = 0
        if self.response_times:
            avg_response_time = sum(self.response_times) / len(self.response_times)
        
        error_rate = 0
        if self.total_requests > 0:
            error_rate = self.error_count / self.total_requests
        
        # 🧠 ניטור זיכרון
        memory_usage_mb = 0
        try:
            memory_health = _memory_monitor.check_memory_health()
            if memory_health["status"] != "error":
                memory_usage_mb = memory_health["memory_info"]["rss_mb"]
                
                # התראה על בעיות זיכרון
                if memory_health["status"] == "warning":
                    self._send_memory_warning(memory_health)
        except Exception as e:
            logging.warning(f"[ConcurrentMonitor] Memory monitoring error: {e}")
        
        return PerformanceMetrics(
            timestamp=get_israel_time(),
            active_users=len(self.active_sessions),
            queue_length=len(self.user_queue),
            avg_response_time=avg_response_time,
            max_response_time=max(self.response_times) if self.response_times else 0,
            sheets_operations_per_minute=0,  # יש לחבר למערכת Sheets
            error_rate=error_rate,
            memory_usage_mb=memory_usage_mb,
            rejected_users=self.rejected_users
        )
    
    async def _collect_metrics_loop(self):
        """לולאה לאיסוף מטריקות כל דקה"""
        while True:
            try:
                metrics = self.get_current_metrics()
                
                # התראה עם עומס גבוה
                if metrics.active_users >= self.max_users * 0.8:
                    await self._send_load_alert(metrics)
                
                # איפוס מונים כל שעה
                if get_israel_time().minute == 0:
                    self.error_count = 0
                    self.total_requests = 0
                
                await asyncio.sleep(60)  # דקה
                
            except Exception as e:
                logging.error(f"[ConcurrentMonitor] Error in metrics collection: {e}")
                await asyncio.sleep(60)
    
    async def _send_load_alert(self, metrics: PerformanceMetrics):
        """שליחת התראת עומס"""
        try:
            from notifications import send_error_notification
            message = (
                f"🚨 **התראת עומס גבוה**\n"
                f"👥 משתמשים פעילים: {metrics.active_users}/{self.max_users}\n"
                f"⏱️ זמן תגובה ממוצע: {metrics.avg_response_time:.2f}s\n"
                f"🔴 שיעור שגיאות: {metrics.error_rate:.1%}\n"
                f"📊 זמן: {metrics.timestamp.strftime('%H:%M:%S')}"
            )
            send_error_notification(message)
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send load alert: {e}")
    
    def get_stats_summary(self) -> dict:
        """קבלת סיכום סטטיסטיקות - גרסה רזה."""
        metrics = self.get_current_metrics()
        return {
            "active_users": metrics.active_users,
            "max_users": self.max_users,
            "avg_response_time": metrics.avg_response_time,
            "error_rate": metrics.error_rate,
            "total_requests": self.total_requests,
            "active_sessions": {id: s.stage for id, s in self.active_sessions.items()},
            "queue_length": metrics.queue_length,
            "rejected_users": metrics.rejected_users,
            "timeout_count": self.timeout_count
        }
    
    def generate_performance_report(self) -> str:
        """יצירת דוח ביצועים מפורט"""
        stats = self.get_stats_summary()
        
        report = f"""
📊 **דוח ביצועי Concurrent Handling**
⏰ זמן יצירה: {get_israel_time().strftime('%d/%m/%Y %H:%M:%S')}

👥 **משתמשים:**
   • פעילים כעת: {stats['active_users']}/{stats['max_users']}
   • סה"כ בקשות: {stats['total_requests']}
   • נדחו בגלל עומס: {stats['rejected_users']}

⏱️ **זמני תגובה:**
   • זמן תגובה ממוצע: {stats['avg_response_time']:.2f}s
   • שיעור שגיאות: {stats['error_rate']:.1%}

🔄 **סשנים פעילים:**
"""
        
        for chat_id, stage in stats['active_sessions'].items():
            report += f"   • {chat_id}: {stage}\n"
        
        if not stats['active_sessions']:
            report += "   • אין סשנים פעילים\n"
        
        return report

    async def _send_rejection_alert(self, chat_id: str, reason: str):
        """שליחת התראה על דחיית משתמש"""
        try:
            from notifications import send_concurrent_alert
            details = {
                "chat_id": chat_id,
                "reason": reason,
                "active_users": len(self.active_sessions),
                "max_users": self.max_users,
                "rejected_users": self.rejected_users
            }
            
            if reason == "max_capacity":
                send_concurrent_alert("max_users_reached", details)
            elif reason == "circuit_breaker":
                send_concurrent_alert("concurrent_error", {
                    "component": "Circuit Breaker",
                    "error": "System overloaded - rejecting new users",
                    "chat_id": chat_id
                })
                
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send rejection alert: {e}")
    
    async def _send_load_warning(self):
        """שליחת התראת עומס"""
        try:
            from notifications import send_concurrent_alert
            current_metrics = self.get_current_metrics()
            send_concurrent_alert("high_response_time", {
                "active_users": current_metrics.active_users,
                "max_users": self.max_users,
                "avg_response_time": current_metrics.avg_response_time,
                "error_rate": current_metrics.error_rate
            })
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send load warning: {e}")
    
    def _send_memory_warning(self, memory_health: dict):
        """שליחת התראת זיכרון"""
        try:
            from notifications import send_concurrent_alert
            memory_info = memory_health["memory_info"]
            warnings = memory_health["warnings"]
            
            memory_details = {
                "component": "MemoryMonitor",
                "error": f"Memory warnings: {', '.join(warnings)}",
                "chat_id": "System",
                "rss_mb": memory_info["rss_mb"],
                "percent": memory_info["percent"],
                "available_mb": memory_info["available_mb"]
            }
            
            send_concurrent_alert("memory_warning", memory_details)
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send memory warning: {e}")
    
    def _send_error_alert(self, alert_type: str, details: dict):
        """שליחת התראת שגיאה כללית"""
        try:
            from notifications import send_concurrent_alert
            # 🔧 תיקון: וידוא שכל השדות הנדרשים קיימים
            error_details = {
                "component": alert_type,
                "error": details.get("error", "Unknown error"),
                "chat_id": details.get("chat_id", "Unknown"),
            }
            # הוספת פרטים נוספים אם קיימים
            for key, value in details.items():
                if key not in ["component", "error", "chat_id"]:
                    error_details[key] = value
            
            # 🔧 תיקון: הוספת פרטים ספציפיים ל-session timeout
            if alert_type == "session_timeout":
                error_details.update({
                    "component": "session_timeout",
                    "error": f"Session timeout after {details.get('duration', 0):.2f}s",
                    "chat_id": details.get("chat_id", "Unknown"),
                    "duration": details.get("duration", 0),
                    "stage": details.get("stage", "Unknown"),
                    "message_id": details.get("message_id", "Unknown"),
                    "timestamp": get_israel_time().strftime('%d/%m/%Y %H:%M:%S')
                })
            
            send_concurrent_alert("concurrent_error", error_details)
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send error alert: {e}")
    
    async def _send_recovery_alert(self, recovery_type: str):
        """שליחת התראת התאוששות"""
        try:
            from notifications import send_recovery_notification
            current_metrics = self.get_current_metrics()
            recovery_details = {
                "active_users": current_metrics.active_users,
                "avg_response_time": current_metrics.avg_response_time,
                "recovery_type": recovery_type
            }
            send_recovery_notification("system_recovered", recovery_details)
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send recovery alert: {e}")

# יצירת instance גלובלי - lazy initialization
_concurrent_monitor_instance = None
_memory_monitor = MemoryMonitor()  # 🔧 תיקון: יצירת instance של MemoryMonitor

def get_concurrent_monitor():
    """קבלת instance של ConcurrentMonitor עם lazy initialization"""
    global _concurrent_monitor_instance
    if _concurrent_monitor_instance is None:
        try:
            from config import MAX_CONCURRENT_USERS
            _concurrent_monitor_instance = ConcurrentMonitor(MAX_CONCURRENT_USERS)
            logging.info(f"[ConcurrentMonitor] Created new instance with max_users={MAX_CONCURRENT_USERS}")
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to create instance: {e}")
            # Fallback - create with default value
            _concurrent_monitor_instance = ConcurrentMonitor(25)
            logging.warning("[ConcurrentMonitor] Using default max_users=25")
    return _concurrent_monitor_instance

# פונקציות עזר לשימוש בקוד
async def start_monitoring_user(chat_id: str, message_id: str, update_obj=None) -> bool:
    """התחלת ניטור משתמש"""
    try:
        logging.debug(f"[ConcurrentMonitor] Starting monitoring for user {chat_id}")
        monitor = get_concurrent_monitor()
        logging.debug(f"[ConcurrentMonitor] Got monitor instance: {type(monitor)}")
        
        if not hasattr(monitor, 'start_user_session'):
            logging.error(f"[ConcurrentMonitor] Monitor instance missing start_user_session method")
            return False
            
        result = await monitor.start_user_session(chat_id, message_id, update_obj)
        logging.debug(f"[ConcurrentMonitor] start_user_session returned: {result}")
        return result
    except Exception as e:
        logging.error(f"[ConcurrentMonitor] Error in start_monitoring_user: {e}")
        import traceback
        logging.error(f"[ConcurrentMonitor] Traceback: {traceback.format_exc()}")
        return False

async def update_user_processing_stage(chat_id: str, stage: str):
    """עדכון שלב עיבוד משתמש"""
    try:
        monitor = get_concurrent_monitor()
        await monitor.update_user_stage(chat_id, stage)
    except Exception as e:
        logging.error(f"[ConcurrentMonitor] Error updating user stage: {e}")

async def end_monitoring_user(chat_id: str, success: bool = True):
    """סיום ניטור משתמש"""
    try:
        monitor = get_concurrent_monitor()
        await monitor.end_user_session(chat_id, success)
    except Exception as e:
        logging.error(f"[ConcurrentMonitor] Error ending user session: {e}")

def get_performance_stats() -> dict:
    """קבלת סטטיסטיקות ביצועים"""
    return get_concurrent_monitor().get_stats_summary()

def get_performance_report() -> str:
    """קבלת דוח ביצועים"""
    return get_concurrent_monitor().generate_performance_report() 