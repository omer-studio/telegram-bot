import psycopg2
import queue
import threading
import json
import logging
from config import config
from simple_config import TimeoutConfig

try:
    from config import should_log_debug_prints
except ImportError:
    def should_log_debug_prints() -> bool:
        return False

DB_URL = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

_metrics_queue = queue.Queue()
_metrics_worker_running = False
_metrics_worker_thread = None

def _metrics_worker():
    global _metrics_worker_running
    _metrics_worker_running = True
    while _metrics_worker_running:
        try:
            metrics_data = _metrics_queue.get(timeout=TimeoutConfig.QUEUE_TIMEOUT)
            if metrics_data is None:
                break
            _save_system_metrics_sync(**metrics_data)
            _metrics_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            if should_log_debug_prints():
                print(f"❌ Worker thread error: {e}")

def _save_system_metrics_sync(metric_type, chat_id=None, **metrics):
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_metrics (
                id SERIAL PRIMARY KEY,
                metric_type VARCHAR(50) NOT NULL,
                chat_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                memory_mb DECIMAL(10,2),
                memory_stage VARCHAR(50),
                response_time_seconds DECIMAL(10,3),
                prep_time_seconds DECIMAL(10,3),
                processing_time_seconds DECIMAL(10,3),
                billing_time_seconds DECIMAL(10,3),
                gpt_latency_seconds DECIMAL(10,3),
                active_sessions INTEGER,
                max_concurrent_users INTEGER,
                avg_response_time DECIMAL(10,3),
                max_response_time DECIMAL(10,3),
                api_calls_count INTEGER,
                api_calls_per_minute INTEGER,
                error_count INTEGER,
                error_type VARCHAR(100),
                timeout_count INTEGER,
                success_count INTEGER,
                additional_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        insert_data = {
            'metric_type': metric_type,
            'chat_id': chat_id,
            'memory_mb': metrics.get('memory_mb'),
            'memory_stage': metrics.get('memory_stage'),
            'response_time_seconds': metrics.get('response_time_seconds'),
            'prep_time_seconds': metrics.get('prep_time_seconds'),
            'processing_time_seconds': metrics.get('processing_time_seconds'),
            'billing_time_seconds': metrics.get('billing_time_seconds'),
            'gpt_latency_seconds': metrics.get('gpt_latency_seconds'),
            'active_sessions': metrics.get('active_sessions'),
            'max_concurrent_users': metrics.get('max_concurrent_users'),
            'avg_response_time': metrics.get('avg_response_time'),
            'max_response_time': metrics.get('max_response_time'),
            'api_calls_count': metrics.get('api_calls_count'),
            'api_calls_per_minute': metrics.get('api_calls_per_minute'),
            'error_count': metrics.get('error_count'),
            'error_type': metrics.get('error_type'),
            'timeout_count': metrics.get('timeout_count'),
            'success_count': metrics.get('success_count'),
            'additional_data': json.dumps(metrics.get('additional_data', {})) if metrics.get('additional_data') else None
        }
        fields = [k for k, v in insert_data.items() if v is not None]
        placeholders = ', '.join(['%s'] * len(fields))
        values = [insert_data[k] for k in fields]
        insert_sql = f"""
        INSERT INTO system_metrics ({', '.join(fields)})
        VALUES ({placeholders})
        """
        cur.execute(insert_sql, values)
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה בשמירת מטריקות {metric_type}: {e}")
        return False

def start_metrics_worker():
    global _metrics_worker_thread, _metrics_worker_running
    if _metrics_worker_thread is not None and _metrics_worker_thread.is_alive():
        return
    _metrics_worker_running = True
    _metrics_worker_thread = threading.Thread(target=_metrics_worker, daemon=True)
    _metrics_worker_thread.start()
    if should_log_debug_prints():
        print("🚀 [METRICS] Background worker started")

def stop_metrics_worker():
    global _metrics_worker_running
    _metrics_worker_running = False
    _metrics_queue.put(None)
    if _metrics_worker_thread and _metrics_worker_thread.is_alive():
        _metrics_worker_thread.join(timeout=TimeoutConfig.THREAD_JOIN_TIMEOUT)

def save_system_metrics(metric_type, chat_id=None, **metrics):
    try:
        if not _metrics_worker_running:
            start_metrics_worker()
        metrics_data = {
            'metric_type': metric_type,
            'chat_id': chat_id,
            **metrics
        }
        _metrics_queue.put(metrics_data, timeout=TimeoutConfig.QUEUE_PUT_TIMEOUT)
        return True
    except queue.Full:
        if should_log_debug_prints():
            print(f"⚠️ [METRICS] Queue full, skipping {metric_type} metric")
        return False
    except Exception as e:
        if should_log_debug_prints():
            print(f"❌ שגיאה בהוספת מטריקה {metric_type}: {e}")
        return False 