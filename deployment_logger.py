#!/usr/bin/env python3
"""
🚀 Deployment Logger - מערכת לוגים מתקדמת לפריסות
שומר כל פלט טרמינל ומידע חשוב במסד הנתונים
"""

import threading
import queue
import json
import os
import sys
import subprocess
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

# Import with fallback for missing modules
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    print("⚠️ psycopg2 not available - database logging disabled")
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

class DeploymentLogger:
    def __init__(self):
        self.log_queue = queue.Queue()
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.commit_hash = self._get_commit_hash()
        self.commit_message = self._get_commit_message()
        self.branch_name = self._get_branch_name()
        self.deployment_id = self._get_deployment_id()
        self.environment = self._detect_environment()
        
        # יצירת הטבלה אם לא קיימת
        self._create_table_if_not_exists()
        
        # Thread רקע לעיבוד הלוגים
        self.worker_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.worker_thread.start()
        
        # רישום התחלת הסשן
        self.log("🚀 Deployment Logger initialized", "INFO", "deployment_logger")
    
    def _get_db_connection(self):
        """קבלת חיבור למסד הנתונים"""
        if not PSYCOPG2_AVAILABLE:
            return None
            
        try:
            # 🔧 תיקון מערכתי: שימוש ב-get_config() מרכזי במקום קריאה קשיחה
            try:
                from config import get_config
                config = get_config()
                db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
            except Exception:
                # fallback לmשתנה סביבה אם get_config() נכשל
                db_url = os.getenv("DATABASE_URL")
            
            if not db_url:
                raise Exception("No database URL found")
            
            return psycopg2.connect(db_url)
        except Exception as e:
            print(f"[DEPLOY_LOG_ERROR] Database connection failed: {e}")
            return None
    
    def _create_table_if_not_exists(self):
        """יצירת טבלת הלוגים אם לא קיימת"""
        try:
            conn = self._get_db_connection()
            if not conn:
                return
            
            cur = conn.cursor()
            cur.execute('''
            CREATE TABLE IF NOT EXISTS deployment_logs (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP,
                session_id TEXT,
                commit_hash TEXT,
                commit_message TEXT,
                branch_name TEXT,
                deployment_id TEXT,
                environment TEXT,
                log_level TEXT,
                source_module TEXT,
                source_function TEXT,
                source_line INTEGER,
                message TEXT,
                user_id TEXT,
                error_type TEXT,
                stack_trace TEXT,
                performance_ms INTEGER,
                memory_mb INTEGER,
                cpu_percent DECIMAL(5,2),
                request_id TEXT,
                ip_address TEXT,
                user_agent TEXT,
                metadata JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            );
            ''')
            
            # יצירת אינדקסים לביצועים
            cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_deployment_logs_session_timestamp 
            ON deployment_logs(session_id, timestamp);
            ''')
            cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_deployment_logs_level_timestamp 
            ON deployment_logs(log_level, timestamp);
            ''')
            cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_deployment_logs_commit_timestamp 
            ON deployment_logs(commit_hash, timestamp);
            ''')
            cur.execute('''
            CREATE INDEX IF NOT EXISTS idx_deployment_logs_source_timestamp 
            ON deployment_logs(source_module, timestamp);
            ''')
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"[DEPLOY_LOG_ERROR] Table creation failed: {e}")
    
    def _get_commit_hash(self) -> str:
        """קבלת hash של הcommit הנוכחי"""
        try:
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                 capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_commit_message(self) -> str:
        """קבלת הודעת הcommit הנוכחי"""
        try:
            result = subprocess.run(['git', 'log', '-1', '--pretty=%B'], 
                                 capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_branch_name(self) -> str:
        """קבלת שם הbranch הנוכחי"""
        try:
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                 capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_deployment_id(self) -> str:
        """קבלת מזהה הפריסה (מ-Render או משתנה סביבה)"""
        return (os.getenv("RENDER_INSTANCE_ID") or 
                os.getenv("DEPLOYMENT_ID") or 
                f"local_{self.session_id}")
    
    def _detect_environment(self) -> str:
        """זיהוי סביבת הריצה"""
        if os.getenv("RENDER"):
            return "render"
        elif os.getenv("HEROKU"):
            return "heroku"
        elif os.getenv("RAILWAY"):
            return "railway"
        elif os.getenv("VERCEL"):
            return "vercel"
        else:
            return "local"
    
    def _get_caller_info(self):
        """קבלת מידע על הקורא (מודול, פונקציה, שורה)"""
        try:
            frame = sys._getframe(3)  # 3 levels up from this function
            return {
                'module': os.path.basename(frame.f_code.co_filename),
                'function': frame.f_code.co_name,
                'line': frame.f_lineno
            }
        except:
            return {'module': 'unknown', 'function': 'unknown', 'line': 0}
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """קבלת מדדי מערכת"""
        try:
            import psutil
            process = psutil.Process()
            return {
                'memory_mb': round(process.memory_info().rss / 1024 / 1024, 1),
                'cpu_percent': round(process.cpu_percent(), 2)
            }
        except:
            return {'memory_mb': 0, 'cpu_percent': 0.0}
    
    def log(self, message: str, level: str = "INFO", source: str = "general", 
            user_id: str = None, performance_ms: int = None, 
            request_id: str = None, metadata: Dict = None, **kwargs):
        """הוספת לוג לתור - לא חוסם!"""
        
        caller_info = self._get_caller_info()
        system_metrics = self._get_system_metrics()
        
        # זיהוי סוג שגיאה אם זה ERROR
        error_type = None
        stack_trace = None
        if level == "ERROR":
            if "Exception" in message or "Error" in message:
                lines = message.split('\n')
                for line in lines:
                    if "Exception:" in line or "Error:" in line:
                        error_type = line.split(':')[0].strip()
                        break
            
            # אם יש traceback זמין
            if hasattr(sys, 'last_traceback') and sys.last_traceback:
                stack_trace = ''.join(traceback.format_tb(sys.last_traceback))
        
        log_entry = {
            'timestamp': datetime.now(),
            'session_id': self.session_id,
            'commit_hash': self.commit_hash,
            'commit_message': self.commit_message,
            'branch_name': self.branch_name,
            'deployment_id': self.deployment_id,
            'environment': self.environment,
            'log_level': level,
            'source_module': caller_info['module'],
            'source_function': caller_info['function'],
            'source_line': caller_info['line'],
            'message': message,
            'user_id': user_id,
            'error_type': error_type,
            'stack_trace': stack_trace,
            'performance_ms': performance_ms,
            'memory_mb': system_metrics['memory_mb'],
            'cpu_percent': system_metrics['cpu_percent'],
            'request_id': request_id,
            'ip_address': kwargs.get('ip_address'),
            'user_agent': kwargs.get('user_agent'),
            'metadata': json.dumps(metadata) if metadata else None
        }
        
        self.log_queue.put(log_entry)
    
    def _process_logs(self):
        """עיבוד לוגים ברקע"""
        while True:
            try:
                log_entry = self.log_queue.get(timeout=1)
                self._save_to_db(log_entry)
                self.log_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # אם יש שגיאה בשמירה - לא נעצור את הבוט!
                print(f"[DEPLOY_LOG_ERROR] Failed to save log: {e}")
    
    def _save_to_db(self, log_entry: Dict):
        """שמירת לוג למסד הנתונים"""
        try:
            conn = self._get_db_connection()
            if not conn:
                return
            
            cur = conn.cursor()
            cur.execute('''
            INSERT INTO deployment_logs (
                timestamp, session_id, commit_hash, commit_message, branch_name,
                deployment_id, environment, log_level, source_module, source_function,
                source_line, message, user_id, error_type, stack_trace,
                performance_ms, memory_mb, cpu_percent, request_id, ip_address,
                user_agent, metadata
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ''', (
                log_entry['timestamp'], log_entry['session_id'], log_entry['commit_hash'],
                log_entry['commit_message'], log_entry['branch_name'], log_entry['deployment_id'],
                log_entry['environment'], log_entry['log_level'], log_entry['source_module'],
                log_entry['source_function'], log_entry['source_line'], log_entry['message'],
                log_entry['user_id'], log_entry['error_type'], log_entry['stack_trace'],
                log_entry['performance_ms'], log_entry['memory_mb'], log_entry['cpu_percent'],
                log_entry['request_id'], log_entry['ip_address'], log_entry['user_agent'],
                log_entry['metadata']
            ))
            
            conn.commit()
            cur.close()
            conn.close()
            
        except Exception as e:
            print(f"[DEPLOY_LOG_ERROR] Database save failed: {e}")
    
    def error(self, message: str, **kwargs):
        """לוג שגיאה"""
        self.log(message, "ERROR", **kwargs)
    
    def warning(self, message: str, **kwargs):
        """לוג אזהרה"""
        self.log(message, "WARNING", **kwargs)
    
    def info(self, message: str, **kwargs):
        """לוג מידע"""
        self.log(message, "INFO", **kwargs)
    
    def debug(self, message: str, **kwargs):
        """לוג דיבוג"""
        self.log(message, "DEBUG", **kwargs)
    
    def performance(self, message: str, duration_ms: int, **kwargs):
        """לוג ביצועים"""
        self.log(message, "PERFORMANCE", performance_ms=duration_ms, **kwargs)
    
    def user_action(self, message: str, user_id: str, **kwargs):
        """לוג פעולת משתמש"""
        self.log(message, "USER_ACTION", user_id=user_id, **kwargs)
    
    def shutdown(self):
        """סגירה נקייה של הלוגר"""
        self.log("🛑 Deployment Logger shutting down", "INFO", "deployment_logger")
        
        # המתנה לסיום עיבוד כל הלוגים
        self.log_queue.join()

# יצירת instance גלובלי
deployment_logger = DeploymentLogger()

# פונקציות נוחות
def log_info(message: str, **kwargs):
    deployment_logger.info(message, **kwargs)

def log_error(message: str, **kwargs):
    deployment_logger.error(message, **kwargs)

def log_warning(message: str, **kwargs):
    deployment_logger.warning(message, **kwargs)

def log_performance(message: str, duration_ms: int, **kwargs):
    deployment_logger.performance(message, duration_ms, **kwargs)

def log_user_action(message: str, user_id: str, **kwargs):
    deployment_logger.user_action(message, user_id, **kwargs) 