#!/usr/bin/env python3
"""
🔥 Live Deployment Logs Monitor - בדיקה חיה של deployment_logs
========================================================================

כלי לבדיקה מהירה ובזמן אמת של הלוגים שנשמרים בטבלת deployment_logs
מראה בדיוק מה קורה ומאשר שהשיקוף עובד

🎯 מטרות:
- בדיקה שהלוגים נשמרים בפועל
- סטטיסטיקות מפורטות
- מעקב אחר לוגים חדשים
- השוואה בין הלוגים השונים

"""

import os
import sys
import time
import psycopg2
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

# Import with fallback for missing modules
try:
    from config import get_config, DB_URL
    CONFIG_AVAILABLE = True
except ImportError:
    print("⚠️ Configuration modules not available - using fallback")
    CONFIG_AVAILABLE = False

class DeploymentLogsMonitor:
    """מוניטור חי לטבלת deployment_logs"""
    
    def __init__(self):
        self.db_url = self._get_db_url()
        self.last_check_time = datetime.now()
        
    def _get_db_url(self) -> str:
        """קבלת URL למסד הנתונים"""
        try:
            if CONFIG_AVAILABLE:
                return DB_URL
            else:
                return os.getenv('DATABASE_URL', '')
        except Exception as e:
            print(f"❌ שגיאה בקבלת DB_URL: {e}")
            return ''
    
    def get_table_stats(self) -> Dict:
        """קבלת סטטיסטיקות כלליות על הטבלה"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            stats = {}
            
            # סה"כ רשומות
            cur.execute("SELECT COUNT(*) FROM deployment_logs")
            stats['total_logs'] = cur.fetchone()[0]
            
            # רשומות מהיום האחרון
            cur.execute("""
                SELECT COUNT(*) FROM deployment_logs 
                WHERE created_at >= NOW() - INTERVAL '1 day'
            """)
            stats['last_24h'] = cur.fetchone()[0]
            
            # רשומות מהשעה האחרונה
            cur.execute("""
                SELECT COUNT(*) FROM deployment_logs 
                WHERE created_at >= NOW() - INTERVAL '1 hour'
            """)
            stats['last_hour'] = cur.fetchone()[0]
            
            # רשומות מ-10 דקות אחרונות
            cur.execute("""
                SELECT COUNT(*) FROM deployment_logs 
                WHERE created_at >= NOW() - INTERVAL '10 minutes'
            """)
            stats['last_10min'] = cur.fetchone()[0]
            
            # סטטיסטיקות לפי מקור
            cur.execute("""
                SELECT source_module, COUNT(*) 
                FROM deployment_logs 
                WHERE created_at >= NOW() - INTERVAL '1 hour'
                GROUP BY source_module 
                ORDER BY COUNT(*) DESC
            """)
            stats['sources_last_hour'] = dict(cur.fetchall())
            
            # סטטיסטיקות לפי level
            cur.execute("""
                SELECT log_level, COUNT(*) 
                FROM deployment_logs 
                WHERE created_at >= NOW() - INTERVAL '1 hour'
                GROUP BY log_level 
                ORDER BY COUNT(*) DESC
            """)
            stats['levels_last_hour'] = dict(cur.fetchall())
            
            # זמן עדכון אחרון
            cur.execute("""
                SELECT MAX(created_at) FROM deployment_logs
            """)
            stats['last_update'] = cur.fetchone()[0]
            
            conn.close()
            return stats
            
        except Exception as e:
            print(f"❌ שגיאה בקבלת סטטיסטיקות: {e}")
            return {}
    
    def get_recent_logs(self, limit: int = 20) -> List[Dict]:
        """קבלת הלוגים האחרונים"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    created_at,
                    timestamp,
                    log_level,
                    source_module,
                    message,
                    environment
                FROM deployment_logs 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
            
            logs = []
            for row in cur.fetchall():
                logs.append({
                    'created_at': row[0],
                    'timestamp': row[1],
                    'log_level': row[2],
                    'source_module': row[3],
                    'message': row[4][:100] + '...' if len(row[4]) > 100 else row[4],
                    'environment': row[5]
                })
            
            conn.close()
            return logs
            
        except Exception as e:
            print(f"❌ שגיאה בקבלת לוגים אחרונים: {e}")
            return []
    
    def get_new_logs_since_last_check(self) -> List[Dict]:
        """קבלת לוגים חדשים מאז הבדיקה האחרונה"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            cur.execute("""
                SELECT 
                    created_at,
                    log_level,
                    source_module,
                    message
                FROM deployment_logs 
                WHERE created_at > %s
                ORDER BY created_at DESC 
                LIMIT 50
            """, (self.last_check_time,))
            
            logs = []
            for row in cur.fetchall():
                logs.append({
                    'created_at': row[0],
                    'log_level': row[1],
                    'source_module': row[2],
                    'message': row[3][:150] + '...' if len(row[3]) > 150 else row[3]
                })
            
            conn.close()
            
            # עדכון זמן בדיקה אחרון
            self.last_check_time = datetime.now()
            
            return logs
            
        except Exception as e:
            print(f"❌ שגיאה בקבלת לוגים חדשים: {e}")
            return []
    
    def check_render_mirror_activity(self) -> Dict:
        """בדיקה פעילות המירור של Render"""
        try:
            conn = psycopg2.connect(self.db_url)
            cur = conn.cursor()
            
            activity = {}
            
            # כמות לוגים מהמירור
            cur.execute("""
                SELECT COUNT(*) FROM deployment_logs 
                WHERE source_module = 'render_api_mirror'
                AND created_at >= NOW() - INTERVAL '1 hour'
            """)
            activity['mirror_logs_last_hour'] = cur.fetchone()[0]
            
            # לוג אחרון מהמירור
            cur.execute("""
                SELECT created_at, message FROM deployment_logs 
                WHERE source_module = 'render_api_mirror'
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            
            result = cur.fetchone()
            if result:
                activity['last_mirror_log'] = {
                    'time': result[0],
                    'message': result[1][:100] + '...' if len(result[1]) > 100 else result[1]
                }
            
            # כמות לוגים מהתפיסה הפנימית
            cur.execute("""
                SELECT COUNT(*) FROM deployment_logs 
                WHERE source_module LIKE 'terminal_%'
                AND created_at >= NOW() - INTERVAL '1 hour'
            """)
            activity['internal_capture_logs_last_hour'] = cur.fetchone()[0]
            
            conn.close()
            return activity
            
        except Exception as e:
            print(f"❌ שגיאה בבדיקת פעילות מירור: {e}")
            return {}
    
    def print_dashboard(self):
        """הדפסת דשבורד מפורט"""
        print("🔥" + "=" * 60)
        print("🔥 DEPLOYMENT LOGS LIVE MONITOR")
        print("🔥" + "=" * 60)
        print(f"🕐 זמן: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        # סטטיסטיקות כלליות
        stats = self.get_table_stats()
        if stats:
            print(f"\n📊 סטטיסטיקות כלליות:")
            print(f"   📋 סה\"כ לוגים: {stats['total_logs']:,}")
            print(f"   📅 יום אחרון: {stats['last_24h']:,}")
            print(f"   ⏰ שעה אחרונה: {stats['last_hour']:,}")
            print(f"   🔥 10 דקות אחרונות: {stats['last_10min']:,}")
            
            if stats.get('last_update'):
                time_diff = datetime.now() - stats['last_update'].replace(tzinfo=None)
                print(f"   📝 עדכון אחרון: {time_diff.total_seconds():.0f} שניות")
        
        # פעילות מירור
        mirror_activity = self.check_render_mirror_activity()
        if mirror_activity:
            print(f"\n🔄 פעילות מירור Render:")
            print(f"   🌐 לוגי API בשעה אחרונה: {mirror_activity.get('mirror_logs_last_hour', 0)}")
            print(f"   💻 לוגי תפיסה פנימית: {mirror_activity.get('internal_capture_logs_last_hour', 0)}")
            
            if mirror_activity.get('last_mirror_log'):
                last_log = mirror_activity['last_mirror_log']
                time_diff = datetime.now() - last_log['time'].replace(tzinfo=None)
                print(f"   📝 לוג אחרון מהמירור: {time_diff.total_seconds():.0f} שניות")
        
        # מקורות לוגים
        if stats.get('sources_last_hour'):
            print(f"\n📈 מקורות לוגים (שעה אחרונה):")
            for source, count in stats['sources_last_hour'].items():
                print(f"   📁 {source}: {count}")
        
        # רמות לוגים
        if stats.get('levels_last_hour'):
            print(f"\n📈 רמות לוגים (שעה אחרונה):")
            for level, count in stats['levels_last_hour'].items():
                icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "DEBUG": "🔍", "PRINT": "📝"}.get(level, "📄")
                print(f"   {icon} {level}: {count}")
    
    def print_recent_logs(self, limit: int = 10):
        """הדפסת לוגים אחרונים"""
        print(f"\n📝 {limit} לוגים אחרונים:")
        print("-" * 60)
        
        logs = self.get_recent_logs(limit)
        
        for i, log in enumerate(logs, 1):
            time_str = log['created_at'].strftime('%H:%M:%S')
            level_icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "DEBUG": "🔍", "PRINT": "📝"}.get(log['log_level'], "📄")
            
            print(f"{i:2d}. [{time_str}] {level_icon} {log['source_module']}")
            print(f"    {log['message']}")
            
        if not logs:
            print("   📭 אין לוגים להצגה")
    
    def monitor_live(self, interval: int = 10):
        """מעקב חי אחר לוגים חדשים"""
        print(f"🔄 מתחיל מעקב חי כל {interval} שניות (Ctrl+C לעצירה)")
        print("-" * 60)
        
        try:
            while True:
                new_logs = self.get_new_logs_since_last_check()
                
                if new_logs:
                    print(f"\n🆕 {len(new_logs)} לוגים חדשים:")
                    for log in new_logs:
                        time_str = log['created_at'].strftime('%H:%M:%S')
                        level_icon = {"ERROR": "❌", "WARNING": "⚠️", "INFO": "ℹ️", "DEBUG": "🔍", "PRINT": "📝"}.get(log['log_level'], "📄")
                        print(f"   [{time_str}] {level_icon} {log['source_module']} | {log['message']}")
                else:
                    print(f"   📭 אין לוגים חדשים ({datetime.now().strftime('%H:%M:%S')})")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n🛑 עצירת מעקב חי")

def main():
    """פונקציה ראשית"""
    print("🔥 === Live Deployment Logs Monitor ===")
    
    monitor = DeploymentLogsMonitor()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "live":
            # מעקב חי
            interval = 10
            if len(sys.argv) > 2:
                try:
                    interval = int(sys.argv[2])
                except:
                    pass
            monitor.monitor_live(interval)
            return
            
        elif command == "recent":
            # לוגים אחרונים בלבד
            limit = 20
            if len(sys.argv) > 2:
                try:
                    limit = int(sys.argv[2])
                except:
                    pass
            monitor.print_recent_logs(limit)
            return
            
        elif command == "stats":
            # סטטיסטיקות בלבד
            stats = monitor.get_table_stats()
            print(json.dumps(stats, indent=2, default=str))
            return
    
    # ברירת מחדל - דשבורד מלא
    monitor.print_dashboard()
    monitor.print_recent_logs(15)
    
    print(f"\n💡 שימושים:")
    print(f"   python {sys.argv[0]} live [seconds]     - מעקב חי")
    print(f"   python {sys.argv[0]} recent [count]     - לוגים אחרונים")
    print(f"   python {sys.argv[0]} stats              - סטטיסטיקות JSON")

if __name__ == "__main__":
    main() 