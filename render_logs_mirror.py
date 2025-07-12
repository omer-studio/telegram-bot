#!/usr/bin/env python3
"""
🔥 Render Logs Mirror - שיקוף מלא בזמן אמת ללוגי Render
====================================================================

מערכת מתקדמת שמושכת כל לוג מ-Render API ושומרת אותו במסד הנתונים
מטרה: שיקוף אחד לאחד ללוגים האמיתיים של Render ללא חסרון

🎯 תכונות:
- שליפה אוטומטית כל דקה
- שמירת כל לוג למסד הנתונים
- מניעת כפילויות
- חסינות לשגיאות
- מעקב אחר לוגים חדשים בלבד
- ביצועים מותאמים

"""

import os
import sys
import time
import json
import requests
import threading
import psycopg2
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
    """מערכת שיקוף לוגי Render בזמן אמת"""
    
    def __init__(self):
        self.running = False
        self.last_sync_time = None
        self.total_logs_synced = 0
        self.api_calls_count = 0
        self.error_count = 0
        self.config = self._load_config()
        self.sync_interval = 60  # שניות - כל דקה
        self.batch_size = 1000  # מקסימום לוגים לבקשה
        
        # וידוא שהטבלה קיימת
        self._ensure_table_exists()
        
        # קבלת הזמן האחרון שנשמר במסד
        self.last_saved_time = self._get_last_saved_time()
        
        logger.info("🔥 Render Logs Mirror initialized")
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
    
    def _save_logs_to_db(self, logs: List[Dict]) -> int:
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
                            'render_mirror',
                            'unknown',
                            'Mirror from Render API',
                            'main',
                            'render_api_sync',
                            'render',
                            level,
                            'render_api_mirror',
                            'fetch_logs',
                            0,
                            message,
                            json.dumps({'original_log': log_entry})
                        ))
                        
                        saved_count += 1
                        
                except Exception as log_error:
                    print(f"⚠️ [MIRROR] שגיאה בשמירת לוג בודד: {log_error}")
                    continue
            
            conn.commit()
            conn.close()
            
            if saved_count > 0:
                print(f"💾 [MIRROR] נשמרו {saved_count} לוגים חדשים למסד הנתונים")
                
            return saved_count
            
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בשמירת לוגים: {e}")
            self.error_count += 1
            return 0
    
    def _sync_once(self):
        """ביצוע סנכרון אחד"""
        try:
            # זמן התחלה לחיפוש
            start_time = self.last_saved_time or (datetime.now() - timedelta(hours=1))
            
            # משיכת לוגים חדשים
            logs = self._fetch_render_logs(start_time)
            
            if logs:
                # שמירת לוגים למסד
                saved_count = self._save_logs_to_db(logs)
                
                if saved_count > 0:
                    self.total_logs_synced += saved_count
                    
                    # עדכון הזמן האחרון
                    latest_log = max(logs, key=lambda x: x.get('timestamp', ''))
                    if latest_log.get('timestamp'):
                        self.last_saved_time = datetime.fromisoformat(
                            latest_log['timestamp'].replace('Z', '+00:00')
                        )
                
                self.last_sync_time = datetime.now()
                
            else:
                print("📋 [MIRROR] אין לוגים חדשים")
                
        except Exception as e:
            print(f"❌ [MIRROR] שגיאה בסנכרון: {e}")
            self.error_count += 1
    
    def start_continuous_sync(self):
        """התחלת סנכרון רציף"""
        print(f"🚀 [MIRROR] מתחיל סנכרון רציף כל {self.sync_interval} שניות")
        self.running = True
        
        while self.running:
            try:
                print(f"\n🔄 [MIRROR] מבצע סנכרון - {datetime.now().strftime('%H:%M:%S')}")
                
                self._sync_once()
                
                # הצגת סטטיסטיקות
                print(f"📊 [MIRROR] סטטיסטיקות:")
                print(f"   📋 סה\"כ לוגים שנשמרו: {self.total_logs_synced}")
                print(f"   🌐 קריאות API: {self.api_calls_count}")
                print(f"   ❌ שגיאות: {self.error_count}")
                print(f"   ⏰ סנכרון אחרון: {self.last_sync_time}")
                
                # המתנה לסנכרון הבא
                print(f"⏳ [MIRROR] ממתין {self.sync_interval} שניות...")
                
                for i in range(self.sync_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n🛑 [MIRROR] התקבל Ctrl+C - עוצר...")
                self.stop()
                break
            except Exception as e:
                print(f"❌ [MIRROR] שגיאה בלולאה ראשית: {e}")
                self.error_count += 1
                time.sleep(10)  # המתנה קצרה לפני ניסיון נוסף
    
    def sync_once_and_exit(self):
        """ביצוע סנכרון אחד ויציאה"""
        print("🔄 [MIRROR] מבצע סנכרון חד-פעמי...")
        self._sync_once()
        print("✅ [MIRROR] סנכרון חד-פעמי הושלם")
    
    def stop(self):
        """עצירת הסנכרון"""
        print("🛑 [MIRROR] עוצר סנכרון...")
        self.running = False
        
        # הצגת סיכום סופי
        print(f"\n📊 [MIRROR] סיכום סופי:")
        print(f"   📋 סה\"כ לוגים שנשמרו: {self.total_logs_synced}")
        print(f"   🌐 קריאות API: {self.api_calls_count}")
        print(f"   ❌ שגיאות: {self.error_count}")
        print(f"   ⏰ זמן ריצה: {datetime.now()}")

def signal_handler(signum, frame):
    """טיפול בסיגנלי מערכת"""
    print(f"\n🛑 התקבל סיגנל {signum} - יוצא...")
    mirror.stop()
    sys.exit(0)

# משתנה גלובלי למירור
mirror = None

def main():
    """פונקציה ראשית"""
    global mirror
    
    print("🔥 === Render Logs Mirror - שיקוף לוגי Render ===")
    print(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 60)
    
    # הגדרת טיפול בסיגנלים
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # יצירת המירור
    mirror = RenderLogsMirror()
    
    # בדיקת ארגומנטים
    if len(sys.argv) > 1:
        if sys.argv[1] == "once":
            mirror.sync_once_and_exit()
            return
        elif sys.argv[1] == "test":
            print("🧪 [MIRROR] מבצע בדיקת חיבור...")
            mirror._sync_once()
            print("✅ [MIRROR] בדיקה הושלמה")
            return
    
    # הפעלת סנכרון רציף
    try:
        mirror.start_continuous_sync()
    except Exception as e:
        print(f"❌ [MIRROR] שגיאה ראשית: {e}")
    finally:
        if mirror:
            mirror.stop()

if __name__ == "__main__":
    main() 