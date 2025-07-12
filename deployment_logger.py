#!/usr/bin/env python3
"""
🚀 Deployment Logger - מערכת לוגים מתקדמת לפריסות
שומר כל פלט טרמינל ומידע חשוב במסד הנתונים

🎯 עדכון חדש: תופס כל print וכל פלט טרמינל ושומר לטבלה!
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
import io

# Import with fallback for missing modules
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    print("⚠️ psycopg2 not available - database logging disabled")
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

class DatabaseStdoutCapture:
    """תופס כל פלט stdout/stderr ושומר לטבלת deployment_logs"""
    
    def __init__(self, deployment_logger, stream_type="stdout"):
        self.deployment_logger = deployment_logger
        self.stream_type = stream_type
        self.original_stream = sys.stdout if stream_type == "stdout" else sys.stderr
        self.is_logging = False  # מניעת לופים אינסופיים
        
    def write(self, message):
        """כתיבה - גם למסך וגם למסד נתונים"""
        try:
            # כתיבה רגילה למסך
            self.original_stream.write(message)
            self.original_stream.flush()
            
            # שמירה למסד נתונים - כל הודעה שאינה שגיאה פנימית
            if (message.strip() and 
                not message.startswith("[DEPLOY_LOG_ERROR]") and
                not self.is_logging):
                
                self.is_logging = True
                try:
                    level = "ERROR" if self.stream_type == "stderr" else "PRINT"
                    # נקודת מפתח: שמירת כל הפלט ללא פילטרים
                    self.deployment_logger.log(
                        message.strip(), 
                        level=level, 
                        source=f"terminal_{self.stream_type}",
                        metadata={"stream_type": self.stream_type, "captured_at": datetime.now().isoformat()}
                    )
                finally:
                    self.is_logging = False
                    
        except Exception as e:
            # אם יש שגיאה בלוגינג - לא נעצור את הבוט!
            if not self.is_logging:  # מניעת לופים אינסופיים
                self.original_stream.write(f"[DEPLOY_LOG_ERROR] Capture failed: {e}\n")
    
    def flush(self):
        """flush למסך"""
        self.original_stream.flush()
    
    def isatty(self):
        """תאימות למסך"""
        return self.original_stream.isatty()

class DeploymentLogger:
    def __init__(self, capture_all_output=True):
        self.log_queue = queue.Queue()
        self.session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.commit_hash = self._get_commit_hash()
        self.commit_message = self._get_commit_message()
        self.branch_name = self._get_branch_name()
        self.deployment_id = self._get_deployment_id()
        self.environment = self._detect_environment()
        self.capture_enabled = capture_all_output
        
        # יצירת הטבלה אם לא קיימת
        self._create_table_if_not_exists()
        
        # Thread רקע לעיבוד הלוגים
        self.worker_thread = threading.Thread(target=self._process_logs, daemon=True)
        self.worker_thread.start()
        
        # רישום התחלת הסשן
        self.log("🚀 Deployment Logger initialized", "INFO", "deployment_logger")
        
        # הפעלת תפיסת הפלט הכללית - מיד ברנדר
        if self.capture_enabled and self.environment == "render":
            self._setup_output_capture()
            self.log("🚀 [DEPLOY] Terminal output capture is now ACTIVE in Render!", "INFO", "deployment_logger")
        elif self.capture_enabled and self.environment != "render":
            self.log("ℹ️ [DEPLOY] Terminal output capture disabled - only active in Render environment", "INFO", "deployment_logger")
    
    def _setup_output_capture(self):
        """הקמת תפיסת כל הפלט לטרמינל"""
        try:
            # שמירת הסטרימים המקוריים
            self.original_stdout = sys.stdout
            self.original_stderr = sys.stderr
            
            # התקנת הwrappers
            sys.stdout = DatabaseStdoutCapture(self, "stdout")
            sys.stderr = DatabaseStdoutCapture(self, "stderr")
            
            # הודעה למסך הרגיל (לא דרך הlogger כדי לא ליצור לוגינג מיותר)
            self.original_stdout.write("📝 [DEPLOY] Output capture enabled - all prints will be saved to deployment_logs\n")
            self.original_stdout.flush()
            
        except Exception as e:
            self.log(f"❌ Failed to setup output capture: {e}", "ERROR", "deployment_logger")
    
    def disable_output_capture(self):
        """השבתת תפיסת הפלט"""
        try:
            if hasattr(self, 'original_stdout'):
                sys.stdout = self.original_stdout
            if hasattr(self, 'original_stderr'):
                sys.stderr = self.original_stderr
                
            self.log("📝 Output capture disabled", "INFO", "deployment_logger")
            
        except Exception as e:
            self.log(f"❌ Failed to disable output capture: {e}", "ERROR", "deployment_logger")

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
            from simple_config import TimeoutConfig
            result = subprocess.run(['git', 'rev-parse', 'HEAD'], 
                                 capture_output=True, text=True, timeout=TimeoutConfig.SUBPROCESS_TIMEOUT_SHORT)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_commit_message(self) -> str:
        """קבלת הודעת הcommit הנוכחי"""
        try:
            from simple_config import TimeoutConfig
            result = subprocess.run(['git', 'log', '-1', '--pretty=%B'], 
                                 capture_output=True, text=True, timeout=TimeoutConfig.SUBPROCESS_TIMEOUT_SHORT)
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"
    
    def _get_branch_name(self) -> str:
        """קבלת שם הbranch הנוכחי"""
        try:
            from simple_config import TimeoutConfig
            result = subprocess.run(['git', 'branch', '--show-current'], 
                                 capture_output=True, text=True, timeout=TimeoutConfig.SUBPROCESS_TIMEOUT_SHORT)
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
                from simple_config import TimeoutConfig
                log_entry = self.log_queue.get(timeout=TimeoutConfig.LOG_QUEUE_TIMEOUT)
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
        
        # השבת הסטרימים המקוריים
        self.disable_output_capture()
        
        # המתנה לסיום עיבוד כל הלוגים
        self.log_queue.join()

# יצירת instance גלובלי - תפיסת פלט מופעלת מיד ברנדר
deployment_logger = DeploymentLogger(capture_all_output=True)

# 🚀 הפעלה מיידית של תפיסת פלט ברנדר
if deployment_logger.environment == "render":
    deployment_logger.original_stdout.write("🚀 [DEPLOY] Deployment Logger fully initialized in Render!\n")
    deployment_logger.original_stdout.flush()
    
    # 🔥 הפעלת מירור לוגי Render בזמן אמת
    try:
        import threading
        import sys
        import os
        
        def start_render_mirror():
            """הפעלת מירור לוגי Render ברקע"""
            try:
                # ייבוא המירור
                sys.path.insert(0, os.path.dirname(__file__))
                from render_logs_mirror import RenderLogsMirror
                
                # יצירת מירור
                mirror = RenderLogsMirror()
                
                # הפעלה ברקע עם interval של 2 דקות (לא לעומס Render)
                mirror.sync_interval = 120
                
                deployment_logger.original_stdout.write("🔥 [DEPLOY] Starting Render API logs mirror...\n")
                deployment_logger.original_stdout.flush()
                
                # הפעלת המירור ברקע
                mirror.start_continuous_sync()
                
            except Exception as e:
                deployment_logger.original_stdout.write(f"⚠️ [DEPLOY] Render mirror failed to start: {e}\n")
                deployment_logger.original_stdout.flush()
        
        # הפעלת המירור בthread נפרד
        mirror_thread = threading.Thread(target=start_render_mirror, daemon=True)
        mirror_thread.start()
        
        deployment_logger.original_stdout.write("🔥 [DEPLOY] Render logs mirror thread started!\n")
        deployment_logger.original_stdout.flush()
        
    except Exception as e:
        deployment_logger.original_stdout.write(f"⚠️ [DEPLOY] Failed to start render mirror: {e}\n")
        deployment_logger.original_stdout.flush()

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

# 🧪 פונקציית בדיקה מיוחדת לפיתוח
def test_capture_functionality():
    """בדיקת תפיסת פלט לפיתוח - נדלק רק ביד"""
    print("🧪 [TEST] מבדק תפיסת פלט - זה אמור להיות בטבלה!")
    print("📝 [TEST] זה print רגיל")
    print("❌ [TEST] זה stderr", file=sys.stderr)
    deployment_logger.log("🧪 [TEST] זה לוג ישיר", "TEST", "test_module")
    print("✅ [TEST] בדיקה הושלמה!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        print("🧪 מריץ בדיקת תפיסת פלט...")
        test_capture_functionality()
        import time
        time.sleep(2)  # תן לworker thread לסיים
        print("🧪 בדיקה הושלמה! בדוק בטבלת deployment_logs") 