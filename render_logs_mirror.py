#!/usr/bin/env python3
"""
🔥 Render Logs Mirror - שיקוף ללוגי Render בפריסה ויומית
====================================================================

מערכת חכמה שמושכת כל לוג מ-Render API בתזמון אופטימלי:
- כל פריסה חדשה (בהתחלת הבוט)
- פעם ביום (מירור יומי מלא)

🎯 תכונות:
- שמירת כל לוג למסד הנתונים
- מניעת כפילויות
- חסינות לשגיאות  
- מעקב אחר לוגים חדשים בלבד
- אופטימיזציה לחיסכון ב-API calls

"""

import os
import sys
import time
import json
import requests
import threading
import psycopg2
import schedule
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import signal

# Import with fallback for missing modules
try:
    from config import get_config, DB_URL
    from simple_config import TimeoutConfig
    from simple_logger import logger
    CONFIG_AVAILABLE = True
except ImportError:
    print("⚠️ Configuration modules not available - using fallback")
    CONFIG_AVAILABLE = False

class RenderLogsMirror:
    """מערכת שיקוף לוגי Render בפריסה ויומית"""
    
    def __init__(self):
        self.total_logs_synced = 0
        self.api_calls_count = 0
        self.error_count = 0
        self.config = self._load_config()
        self.batch_size = 2000  # יותר לוגים בפריסה/יומית
        
        # וידוא שהטבלה קיימת
        self._ensure_table_exists()
        
        # קבלת הזמן האחרון שנשמר במסד
        self.last_saved_time = self._get_last_saved_time()
        
        if CONFIG_AVAILABLE:
            logger.info("🔥 Render Logs Mirror initialized (deployment + daily)")
        print(f"🔥 [MIRROR] מערכת שיקוף לוגי Render הופעלה")
        print(f"📅 [MIRROR] זמן אחרון שנשמר: {self.last_saved_time}")
    
    def _load_config(self) -> Dict:
        """טעינת קונפיגורציה"""
        try:
            if CONFIG_AVAILABLE:
                config = get_config()
                return {
                    'api_key': config.get('RENDER_API_KEY'),
                    'service_id': config.get('RENDER_SERVICE_ID'),
                    'db_url': DB_URL
                }
            else:
                return {
                    'api_key': os.getenv('RENDER_API_KEY'),
                    'service_id': os.getenv('RENDER_SERVICE_ID'),
                    'db_url': os.getenv('DATABASE_URL')
                }
        except Exception as e:
            print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
            return {}
    
    def _ensure_table_exists(self):
        """וידוא שטבלת deployment_logs קיימת"""
        try:
            conn = psycopg2.connect(self.config['db_url'])
            cur = conn.cursor()
            
            # בדיקה אם הטבלה קיימת
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'deployment_logs'
                )
            """)
            
            table_exists = cur.fetchone()[0]
            
            if table_exists:
                print("✅ [MIRROR] טבלת deployment_logs קיימת")
            else:
                print("❌ [MIRROR] טבלת deployment_logs לא קיימת - יש ליצור אותה קודם")
                
            conn.close()
            
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בבדיקת טבלה: {e}")
    
    def _get_last_saved_time(self) -> Optional[datetime]:
        """קבלת הזמן האחרון שנשמר במסד"""
        try:
            conn = psycopg2.connect(self.config['db_url'])
            cur = conn.cursor()
            
            cur.execute("""
                SELECT MAX(timestamp) FROM deployment_logs 
                WHERE source_module = 'render_api_mirror'
            """)
            
            result = cur.fetchone()[0]
            conn.close()
            
            if result:
                print(f"📅 [MIRROR] נמצא זמן אחרון: {result}")
                return result
            else:
                # אם אין נתונים, התחל מ-24 שעות אחורה  
                start_time = datetime.now() - timedelta(hours=24)
                print(f"📅 [MIRROR] התחלה מ-24 שעות אחורה: {start_time}")
                return start_time
                
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בקבלת זמן אחרון: {e}")
            return datetime.now() - timedelta(hours=1)
    
    def _fetch_render_logs(self, start_time: datetime) -> List[Dict]:
        """משיכת לוגים מ-Render API"""
        try:
            if not self.config.get('api_key') or not self.config.get('service_id'):
                print("❌ [MIRROR] חסרים נתוני API של Render")
                return []
            
            headers = {
                'Authorization': f"Bearer {self.config['api_key']}",
                'Accept': 'application/json'
            }
            
            url = f"https://api.render.com/v1/services/{self.config['service_id']}/logs"
            
            params = {
                'startTime': start_time.isoformat() + 'Z',
                'limit': self.batch_size
            }
            
            timeout = TimeoutConfig.RENDER_LOGS_TIMEOUT if CONFIG_AVAILABLE else 30
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
            
            self.api_calls_count += 1
            
            if response.status_code == 200:
                data = response.json()
                logs = data.get('logs', [])
                print(f"📋 [MIRROR] נמשכו {len(logs)} לוגים מ-{start_time.strftime('%H:%M:%S')}")
                return logs
            else:
                print(f"❌ [MIRROR] שגיאה בAPI: {response.status_code} - {response.text}")
                self.error_count += 1
                return []
                
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה במשיכת לוגים: {e}")
            self.error_count += 1
            return []
    
    def _save_logs_to_db(self, logs: List[Dict], sync_type: str = "manual") -> int:
        """שמירת לוגים למסד הנתונים"""
        if not logs:
            return 0
            
        try:
            conn = psycopg2.connect(self.config['db_url'])
            cur = conn.cursor()
            
            saved_count = 0
            
            for log_entry in logs:
                try:
                    # חילוץ מידע מהלוג
                    timestamp = log_entry.get('timestamp')
                    message = log_entry.get('message', '')
                    level = log_entry.get('level', 'INFO')
                    
                    # המרת timestamp
                    if timestamp:
                        if isinstance(timestamp, str):
                            # אם זה string, ננסה לפרש אותו
                            try:
                                timestamp_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                            except:
                                timestamp_dt = datetime.now()
                        else:
                            timestamp_dt = timestamp
                    else:
                        timestamp_dt = datetime.now()
                    
                    # בדיקה שהלוג לא קיים כבר
                    cur.execute("""
                        SELECT COUNT(*) FROM deployment_logs 
                        WHERE timestamp = %s AND message = %s AND source_module = 'render_api_mirror'
                    """, (timestamp_dt, message))
                    
                    exists = cur.fetchone()[0]
                    
                    if exists == 0:
                        # שמירת הלוג
                        cur.execute("""
                            INSERT INTO deployment_logs (
                                timestamp, session_id, commit_hash, commit_message, 
                                branch_name, deployment_id, environment, log_level, 
                                source_module, source_function, source_line, message, 
                                metadata, created_at
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                            )
                        """, (
                            timestamp_dt,
                            f'render_mirror_{sync_type}',
                            'unknown',
                            f'Mirror from Render API ({sync_type})',
                            'main',
                            f'render_api_sync_{sync_type}',
                            'render',
                            level,
                            'render_api_mirror',
                            f'sync_{sync_type}',
                            0,
                            message,
                            json.dumps({'original_log': log_entry, 'sync_type': sync_type})
                        ))
                        
                        saved_count += 1
                        
                except Exception as log_error:
                    print(f"⚠️ [MIRROR] שגיאה בשמירת לוג בודד: {log_error}")
                    continue
            
            conn.commit()
            conn.close()
            
            if saved_count > 0:
                print(f"💾 [MIRROR] נשמרו {saved_count} לוגים חדשים ({sync_type})")
                
            return saved_count
            
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בשמירת לוגים: {e}")
            self.error_count += 1
            return 0
    
    def sync_deployment_logs(self) -> int:
        """סנכרון לוגים בפריסה - מאז הפעם האחרונה"""
        print("🚀 [MIRROR] מבצע סנכרון פריסה...")
        
        try:
            # זמן התחלה - מאז הפעם האחרונה
            start_time = self.last_saved_time or (datetime.now() - timedelta(hours=4))
            
            # משיכת לוגים חדשים
            logs = self._fetch_render_logs(start_time)
            
            if logs:
                # שמירת לוגים למסד
                saved_count = self._save_logs_to_db(logs, "deployment")
                
                if saved_count > 0:
                    self.total_logs_synced += saved_count
                    
                    # עדכון הזמן האחרון
                    latest_log = max(logs, key=lambda x: x.get('timestamp', ''))
                    if latest_log.get('timestamp'):
                        self.last_saved_time = datetime.fromisoformat(
                            latest_log['timestamp'].replace('Z', '+00:00')
                        )
                
                print(f"✅ [MIRROR] סנכרון פריסה הושלם: {saved_count} לוגים חדשים")
                return saved_count
            else:
                print("📭 [MIRROR] אין לוגים חדשים בפריסה")
                return 0
                
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בסנכרון פריסה: {e}")
            self.error_count += 1
            return 0
    
    def sync_daily_logs(self) -> int:
        """סנכרון יומי מלא - 24 שעות אחרונות"""
        print("📅 [MIRROR] מבצע סנכרון יומי...")
        
        try:
            # זמן התחלה - 24 שעות אחורה
            start_time = datetime.now() - timedelta(hours=24)
            
            # משיכת לוגים
            logs = self._fetch_render_logs(start_time)
            
            if logs:
                # שמירת לוגים למסד (רק חדשים)
                saved_count = self._save_logs_to_db(logs, "daily")
                
                if saved_count > 0:
                    self.total_logs_synced += saved_count
                
                print(f"✅ [MIRROR] סנכרון יומי הושלם: {saved_count} לוגים חדשים")
                return saved_count
            else:
                print("📭 [MIRROR] אין לוגים חדשים בסנכרון יומי")
                return 0
                
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בסנכרון יומי: {e}")
            self.error_count += 1
            return 0
    
    def setup_daily_scheduler(self):
        """הגדרת תזמון יומי לסנכרון"""
        try:
            # תזמון לשעה 02:00 בלילה כל יום
            schedule.every().day.at("02:00").do(self.sync_daily_logs)
            
            print("⏰ [MIRROR] תזמון יומי הוגדר ל-02:00")
            
            # רץ ברקע
            def run_scheduler():
                while True:
                    schedule.run_pending()
                    time.sleep(3600)  # בדיקה כל שעה
            
            scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
            scheduler_thread.start()
            
            print("✅ [MIRROR] תזמון יומי פעיל")
            
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בהגדרת תזמון: {e}")
    
    def get_stats(self) -> Dict:
        """קבלת סטטיסטיקות המירור"""
        return {
            'total_logs_synced': self.total_logs_synced,
            'api_calls_count': self.api_calls_count,
            'error_count': self.error_count,
            'last_saved_time': self.last_saved_time
        }

# Instance גלובלי למירור
mirror_instance = None

def get_render_mirror():
    """קבלת instance של המירור (singleton)"""
    global mirror_instance
    if mirror_instance is None:
        mirror_instance = RenderLogsMirror()
    return mirror_instance

def sync_on_deployment():
    """סנכרון בפריסה - נקרא מ-deployment_logger"""
    try:
        mirror = get_render_mirror()
        saved_count = mirror.sync_deployment_logs()
        print(f"🚀 [MIRROR] פריסה: {saved_count} לוגים נוספו")
        return saved_count
    except Exception as e:
        print(f"❌ [MIRROR] שגיאה בסנכרון פריסה: {e}")
        return 0

def setup_daily_sync():
    """הגדרת סנכרון יומי - נקרא מ-deployment_logger"""
    try:
        mirror = get_render_mirror()
        mirror.setup_daily_scheduler()
        print("⏰ [MIRROR] תזמון יומי הוגדר")
    except Exception as e:
        print(f"❌ [MIRROR] שגיאה בהגדרת תזמון יומי: {e}")

def main():
    """פונקציה ראשית לבדיקות ידניות"""
    print("🔥 === Render Logs Mirror - פריסה ויומית ===")
    print(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    mirror = get_render_mirror()
    
    # בדיקת ארגומנטים
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "deployment":
            print("🚀 [MIRROR] מבצע סנכרון פריסה ידני...")
            saved_count = mirror.sync_deployment_logs()
            print(f"✅ [MIRROR] הושלם: {saved_count} לוגים")
            return
            
        elif command == "daily":
            print("📅 [MIRROR] מבצע סנכרון יומי ידני...")
            saved_count = mirror.sync_daily_logs()
            print(f"✅ [MIRROR] הושלם: {saved_count} לוגים")
            return
            
        elif command == "setup":
            print("⏰ [MIRROR] מגדיר תזמון יומי...")
            mirror.setup_daily_scheduler()
            print("✅ [MIRROR] תזמון הוגדר - ממתין...")
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                print("\n🛑 [MIRROR] תזמון הופסק")
            return
            
        elif command == "stats":
            print("📊 [MIRROR] סטטיסטיקות:")
            stats = mirror.get_stats()
            for key, value in stats.items():
                print(f"   {key}: {value}")
            return
    
    # ברירת מחדל - סנכרון פריסה
    print("🚀 [MIRROR] מבצע סנכרון פריסה (ברירת מחדל)...")
    saved_count = mirror.sync_deployment_logs()
    print(f"✅ [MIRROR] הושלם: {saved_count} לוגים")
    
    # הוראות שימוש
    print(f"\n💡 שימושים:")
    print(f"   python {sys.argv[0]} deployment    - סנכרון פריסה")
    print(f"   python {sys.argv[0]} daily         - סנכרון יומי") 
    print(f"   python {sys.argv[0]} setup         - הגדרת תזמון יומי")
    print(f"   python {sys.argv[0]} stats         - סטטיסטיקות")

if __name__ == "__main__":
    main() 