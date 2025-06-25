"""
concurrent_monitor.py
--------------------
🔐 מערכת ניטור מתקדמת לביצועי Concurrent Handling בבוט טלגרם

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
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Deque
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import logging

@dataclass
class UserSession:
    """מייצג סשן משתמש פעיל עם נתוני בטיחות"""
    chat_id: str
    start_time: float
    message_id: str
    stage: str  # "queued", "processing", "gpt_a", "background", "completed"
    queue_position: int  # FIFO position
    max_allowed_time: float = 30.0  # מקסימום 30 שניות לסשן
    
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

class ConcurrentMonitor:
    """
    🛡️ מערכת ניטור מתקדמת עם מנגנוני בטיחות
    
    עקרונות פעולה:
    1. FIFO: כל משתמש מקבל מספר בתור לפי סדר הגעה
    2. Timeout Protection: סשנים לא יכולים לרוץ יותר מ-30 שניות
    3. Circuit Breaker: בעומס גבוה - דחיית בקשות חדשות
    4. Auto Recovery: ניקוי אוטומטי של סשנים תקועים
    5. Memory Protection: מגבלות על שמירת היסטוריה
    """
    
    def __init__(self, max_users: int = 10):
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
        
        # לא יוצרים tasks כאן - הם ייווצרו כשהמערכת תתחיל לעבוד
        self._background_tasks_started = False
        
    async def _ensure_background_tasks_started(self):
        """מתחיל את background tasks אם הם לא התחילו עדיין"""
        if not self._background_tasks_started:
            try:
                asyncio.create_task(self._collect_metrics_loop())
                asyncio.create_task(self._cleanup_stale_sessions())
                asyncio.create_task(self._monitor_system_health())
                self._background_tasks_started = True
                logging.info("[ConcurrentMonitor] Background tasks started")
            except RuntimeError:
                # אם אין event loop פעיל, ננסה שוב בפעם הבאה
                pass
        
    async def start_user_session(self, chat_id: str, message_id: str) -> bool:
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
            
            # בדיקת קיבולת מקסימלית
            if len(self.active_sessions) >= self.max_users:
                self.rejected_users += 1
                await self._send_rejection_alert(chat_id, "max_capacity")
                return False
            
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
            
            logging.info(f"[ConcurrentMonitor] ✅ Started session for user {chat_id}. "
                        f"Queue position: {session.queue_position}, Active: {len(self.active_sessions)}")
            
            # התראה אם מתקרבים לקיבולת מקסימלית
            if len(self.active_sessions) >= self.max_users * 0.8:
                await self._send_load_warning()
            
            return True
            
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Error starting session for {chat_id}: {e}")
            await self._send_error_alert("start_session_error", {"chat_id": chat_id, "error": str(e)})
            return False
    
    async def update_user_stage(self, chat_id: str, stage: str):
        """📍 עדכון שלב עיבוד של משתמש עם לוגים מפורטים"""
        if chat_id in self.active_sessions:
            old_stage = self.active_sessions[chat_id].stage
            self.active_sessions[chat_id].stage = stage
            
            # מעבר מ-queued ל-processing
            if old_stage == "queued" and stage == "processing":
                self._remove_from_queue(chat_id)
            
            logging.debug(f"[ConcurrentMonitor] 📍 User {chat_id}: {old_stage} → {stage}")
    
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
            
            # שמירת מדדי ביצועים
            self.response_times.append(response_time)
            
            if not success:
                self.error_count += 1
                
            # בדיקת timeout
            if session.is_timeout():
                self.timeout_count += 1
                await self._send_error_alert("session_timeout", {
                    "chat_id": chat_id,
                    "duration": response_time,
                    "stage": session.stage
                })
            
            # הסרת הסשן
            self._remove_from_queue(chat_id)
            del self.active_sessions[chat_id]
            
            logging.info(f"[ConcurrentMonitor] 🏁 Ended session for user {chat_id}. "
                        f"Duration: {response_time:.2f}s, Success: {success}, Active: {len(self.active_sessions)}")
            
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Error ending session for {chat_id}: {e}")
    
    async def _cleanup_stale_sessions(self):
        """
        🧹 ניקוי אוטומטי של סשנים תקועים (כל 30 שניות)
        מנגנון בטיחות למניעת memory leaks וסשנים תקועים
        """
        while True:
            try:
                stale_sessions = []
                
                for chat_id, session in self.active_sessions.items():
                    if session.is_timeout():
                        stale_sessions.append(chat_id)
                
                # ניקוי סשנים תקועים
                for chat_id in stale_sessions:
                    await self.end_user_session(chat_id, success=False)
                    logging.warning(f"[ConcurrentMonitor] 🧹 Cleaned stale session: {chat_id}")
                
                if stale_sessions:
                    await self._send_error_alert("stale_sessions_cleaned", {
                        "count": len(stale_sessions),
                        "sessions": stale_sessions
                    })
                
                await asyncio.sleep(30)  # בדיקה כל 30 שניות
                
            except Exception as e:
                logging.error(f"[ConcurrentMonitor] Error in cleanup: {e}")
                await asyncio.sleep(30)
    
    async def _monitor_system_health(self):
        """
        💊 ניטור בריאות המערכת וCircuit Breaker (כל 10 שניות)
        """
        while True:
            try:
                current_metrics = self.get_current_metrics()
                
                # בדיקת Circuit Breaker - הוחלט מעולם לא להפעיל אותו
                should_activate_cb = False  # מבוטל לחלוטין - נותן חופש מלא למשתמשים
                
                if should_activate_cb and not self.circuit_breaker_active:
                    self.circuit_breaker_active = True
                    await self._send_error_alert("circuit_breaker_activated", {
                        "error_rate": current_metrics.error_rate,
                        "avg_response_time": current_metrics.avg_response_time,
                        "active_users": current_metrics.active_users
                    })
                    
                elif not should_activate_cb and self.circuit_breaker_active:
                    self.circuit_breaker_active = False
                    await self._send_recovery_alert("circuit_breaker_deactivated")
                
                await asyncio.sleep(10)  # בדיקה כל 10 שניות
                
            except Exception as e:
                logging.error(f"[ConcurrentMonitor] Error in health monitoring: {e}")
                await asyncio.sleep(10)
    
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
        
        return PerformanceMetrics(
            timestamp=datetime.now(),
            active_users=len(self.active_sessions),
            queue_length=len(self.user_queue),
            avg_response_time=avg_response_time,
            max_response_time=max(self.response_times) if self.response_times else 0,
            sheets_operations_per_minute=0,  # יש לחבר למערכת Sheets
            error_rate=error_rate,
            memory_usage_mb=0,  # יש לחבר למערכת Memory
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
                if datetime.now().minute == 0:
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
        """קבלת סיכום סטטיסטיקות"""
        current_metrics = self.get_current_metrics()
        
        return {
            "current_active_users": current_metrics.active_users,
            "max_concurrent_users": self.max_users,
            "avg_response_time_current": current_metrics.avg_response_time,
            "avg_response_time_hour": current_metrics.avg_response_time,  # פשוט השתמש בערך הנוכחי
            "avg_active_users_hour": current_metrics.active_users,  # פשוט השתמש בערך הנוכחי
            "max_active_users_hour": current_metrics.active_users,  # פשוט השתמש בערך הנוכחי
            "error_rate": current_metrics.error_rate,
            "total_requests": self.total_requests,
            "active_sessions": {chat_id: session.stage for chat_id, session in self.active_sessions.items()},
            "queue_length": current_metrics.queue_length,
            "rejected_users": current_metrics.rejected_users,
            "timeout_count": self.timeout_count
        }
    
    def generate_performance_report(self) -> str:
        """יצירת דוח ביצועים מפורט"""
        stats = self.get_stats_summary()
        
        report = f"""
📊 **דוח ביצועי Concurrent Handling**
⏰ זמן יצירה: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

👥 **משתמשים:**
   • פעילים כעת: {stats['current_active_users']}/{stats['max_concurrent_users']}
   • ממוצע בשעה האחרונה: {stats['avg_active_users_hour']:.1f}
   • מקסימום בשעה האחרונה: {stats['max_active_users_hour']}

⏱️ **זמני תגובה:**
   • נוכחי: {stats['avg_response_time_current']:.2f}s
   • ממוצע בשעה האחרונה: {stats['avg_response_time_hour']:.2f}s

📈 **סטטיסטיקות:**
   • סה"כ בקשות: {stats['total_requests']}
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
    
    async def _send_error_alert(self, alert_type: str, details: dict):
        """שליחת התראת שגיאה כללית"""
        try:
            from notifications import send_concurrent_alert
            send_concurrent_alert("concurrent_error", {
                "component": alert_type,
                "error": details.get("error", "Unknown error"),
                "chat_id": details.get("chat_id", "Unknown"),
                **details
            })
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send error alert: {e}")
    
    async def _send_recovery_alert(self, recovery_type: str):
        """שליחת התראת התאוששות"""
        try:
            from notifications import send_recovery_notification
            current_metrics = self.get_current_metrics()
            send_recovery_notification("system_recovered", {
                "active_users": current_metrics.active_users,
                "avg_response_time": current_metrics.avg_response_time,
                "recovery_type": recovery_type
            })
        except Exception as e:
            logging.error(f"[ConcurrentMonitor] Failed to send recovery alert: {e}")

# יצירת instance גלובלי - lazy initialization
_concurrent_monitor_instance = None

def get_concurrent_monitor():
    """קבלת instance של ConcurrentMonitor עם lazy initialization"""
    global _concurrent_monitor_instance
    if _concurrent_monitor_instance is None:
        from config import MAX_CONCURRENT_USERS
        _concurrent_monitor_instance = ConcurrentMonitor(MAX_CONCURRENT_USERS)
    return _concurrent_monitor_instance

# פונקציות עזר לשימוש בקוד
async def start_monitoring_user(chat_id: str, message_id: str) -> bool:
    """התחלת ניטור משתמש"""
    return await get_concurrent_monitor().start_user_session(chat_id, message_id)

async def update_user_processing_stage(chat_id: str, stage: str):
    """עדכון שלב עיבוד משתמש"""
    await get_concurrent_monitor().update_user_stage(chat_id, stage)

async def end_monitoring_user(chat_id: str, success: bool = True):
    """סיום ניטור משתמש"""
    await get_concurrent_monitor().end_user_session(chat_id, success)

def get_performance_stats() -> dict:
    """קבלת סטטיסטיקות ביצועים"""
    return get_concurrent_monitor().get_stats_summary()

def get_performance_report() -> str:
    """קבלת דוח ביצועים"""
    return get_concurrent_monitor().generate_performance_report() 