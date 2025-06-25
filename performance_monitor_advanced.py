"""
performance_monitor_advanced.py
-------------------------------
מערכת אבחון צוואר בקבוק מתקדמת - עם תמיכה ב-streaming
=========================================================
גרסה מתקדמת של מערכת מדידת הביצועים עם:
1. מדידת TTFT מדויקת באמצעות streaming
2. ניטור זמן אמת של TPS במהלך יצירת התגובה
3. ניתוח מפורט יותר של דפוסי ביצועים
4. זיהוי אוטומטי של סוגי צוואר בקבוק שונים
"""

import time
import json
import logging
import asyncio
from typing import Dict, AsyncGenerator, Optional
from dataclasses import dataclass
from performance_monitor import PerformanceMonitor, PerformanceMetrics, performance_monitor
import litellm

class StreamingPerformanceMonitor(PerformanceMonitor):
    """
    מנטר ביצועים מתקדם עם תמיכה במדידת streaming מדויקת
    """
    
    def __init__(self, target_samples: int = 100):
        super().__init__(target_samples)
        self.streaming_measurements: Dict[str, Dict] = {}
    
    async def measure_streaming_response(self, full_messages, model, completion_params, measurement_id):
        """
        מודד ביצועים במהלך streaming response
        מחזיר את התגובה המלאה + מדידות מדויקות
        """
        if measurement_id not in self.active_measurements:
            logging.warning(f"🔬 Measurement ID not found: {measurement_id}")
            return None
        
        try:
            # הוספת streaming לפרמטרים
            stream_params = completion_params.copy()
            stream_params['stream'] = True
            
            # התחלת הבקשה
            request_start = time.time()
            response_stream = litellm.completion(**stream_params)
            
            # משתנים למעקב
            first_token_received = False
            tokens_received = 0
            content_chunks = []
            last_chunk_time = time.time()
            token_times = []
            
            # עיבוד ה-stream
            async for chunk in response_stream:
                current_time = time.time()
                
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    content_chunks.append(content)
                    
                    # רישום הטוקן הראשון
                    if not first_token_received:
                        first_token_received = True
                        self.record_first_token(measurement_id)
                        logging.info(f"🔬 First token received after {current_time - request_start:.3f}s")
                    
                    # חישוב TPS זמני
                    if tokens_received > 0:
                        time_since_last = current_time - last_chunk_time
                        if time_since_last > 0:
                            # הערכת מספר טוקנים בחלק הזה (גס אך מועיל)
                            estimated_tokens = len(content) / 3.5  # הערכה גסה
                            instantaneous_tps = estimated_tokens / time_since_last
                            token_times.append({
                                'time': current_time,
                                'estimated_tps': instantaneous_tps,
                                'content_length': len(content)
                            })
                    
                    tokens_received += 1
                    last_chunk_time = current_time
            
            # איסוף המידע הסופי
            full_content = ''.join(content_chunks)
            total_response_time = time.time() - request_start
            
            # רישום סטטיסטיקות streaming נוספות
            if measurement_id in self.active_measurements:
                self.streaming_measurements[measurement_id] = {
                    'total_chunks': tokens_received,
                    'avg_chunk_interval': total_response_time / max(tokens_received, 1),
                    'token_timing_data': token_times[-10:],  # שמירת 10 האחרונים
                    'content_length': len(full_content),
                    'estimated_tokens_by_length': len(full_content) / 3.5
                }
            
            return {
                'content': full_content,
                'total_response_time': total_response_time,
                'chunks_received': tokens_received,
                'first_token_time': time.time() if first_token_received else None
            }
            
        except Exception as e:
            logging.error(f"🔬 Streaming measurement failed: {e}")
            # חזרה למדידה רגילה במקרה של כישלון
            return None
    
    def get_detailed_analysis(self) -> Dict:
        """
        ניתוח מפורט יותר הכולל נתוני streaming
        """
        base_analysis = super().analyze_performance()
        
        if "error" in base_analysis:
            return base_analysis
        
        # הוספת ניתוח streaming מתקדם
        streaming_data = []
        for measurement_id, stream_info in self.streaming_measurements.items():
            streaming_data.append(stream_info)
        
        if streaming_data:
            # ניתוח דפוסי זמני TPS
            avg_chunk_intervals = [d['avg_chunk_interval'] for d in streaming_data]
            
            base_analysis['streaming_analysis'] = {
                'total_streaming_measurements': len(streaming_data),
                'avg_chunk_interval': sum(avg_chunk_intervals) / len(avg_chunk_intervals),
                'response_consistency': self._analyze_consistency(streaming_data),
                'streaming_efficiency': self._analyze_streaming_efficiency(streaming_data)
            }
        
        return base_analysis
    
    def _analyze_consistency(self, streaming_data) -> Dict:
        """
        מנתח עקביות ביצועי streaming
        """
        if not streaming_data:
            return {}
        
        intervals = [d['avg_chunk_interval'] for d in streaming_data]
        mean_interval = sum(intervals) / len(intervals)
        
        # חישוב סטיית תקן
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_dev = variance ** 0.5
        
        consistency_score = 1 - (std_dev / mean_interval) if mean_interval > 0 else 0
        
        return {
            'consistency_score': consistency_score,
            'interpretation': 'יציב' if consistency_score > 0.8 else 'בינוני' if consistency_score > 0.6 else 'לא יציב',
            'std_deviation': std_dev,
            'mean_interval': mean_interval
        }
    
    def _analyze_streaming_efficiency(self, streaming_data) -> Dict:
        """
        מנתח יעילות תהליך ה-streaming
        """
        if not streaming_data:
            return {}
        
        total_chunks = sum(d['total_chunks'] for d in streaming_data)
        total_content = sum(d['content_length'] for d in streaming_data)
        
        avg_content_per_chunk = total_content / max(total_chunks, 1)
        
        efficiency_score = min(avg_content_per_chunk / 10, 1.0)  # ציון יעילות יחסי
        
        return {
            'avg_content_per_chunk': avg_content_per_chunk,
            'efficiency_score': efficiency_score,
            'interpretation': 'יעיל' if efficiency_score > 0.7 else 'בינוני' if efficiency_score > 0.4 else 'לא יעיל',
            'total_measurements': len(streaming_data)
        }

# פונקציית עזר לשימוש ב-GPT handlers
async def measure_gpt_response_with_streaming(full_messages, model, completion_params, chat_id, message_id):
    """
    פונקציית עזר למדידת תגובת GPT עם streaming
    להשתמש מ-gpt_a_handler במקום הגרסה הרגילה
    """
    # יצירת measurement_id
    user_message = full_messages[-1]["content"] if full_messages else ""
    measurement_id = performance_monitor.start_measurement(
        chat_id=str(chat_id),
        message_id=str(message_id),
        user_message=user_message
    )
    
    # שימוש במנטר המתקדם אם זמין
    if hasattr(performance_monitor, 'measure_streaming_response'):
        try:
            result = await performance_monitor.measure_streaming_response(
                full_messages, model, completion_params, measurement_id
            )
            
            if result:
                # השלמת המדידה עם הנתונים האמיתיים
                # כאן נצטרך לעדכן עם נתוני usage אמיתיים מה-response
                performance_monitor.record_response_complete(
                    measurement_id=measurement_id,
                    prompt_tokens=0,  # יעודכן מהresponse האמיתי
                    completion_tokens=int(result.get('estimated_tokens_by_length', 0)),
                    model_used=model,
                    model_tier="streaming"
                )
                
                return result['content']
        except Exception as e:
            logging.error(f"🔬 Streaming measurement failed, falling back to regular: {e}")
    
    # fallback למדידה רגילה
    try:
        response = litellm.completion(**completion_params)
        performance_monitor.record_first_token(measurement_id)
        
        content = response.choices[0].message.content.strip()
        
        performance_monitor.record_response_complete(
            measurement_id=measurement_id,
            prompt_tokens=getattr(response.usage, 'prompt_tokens', 0),
            completion_tokens=getattr(response.usage, 'completion_tokens', 0),
            model_used=response.model,
            model_tier="regular"
        )
        
        return content
        
    except Exception as e:
        performance_monitor.record_error(measurement_id, str(e))
        raise

# יצירת instance מתקדם
advanced_performance_monitor = StreamingPerformanceMonitor()

# פונקציה לשדרוג המנטר הקיים
def upgrade_to_advanced_monitor():
    """
    משדרג את המנטר הקיים לגרסה המתקדמת
    """
    global performance_monitor
    
    # העברת נתונים קיימים
    current_data = performance_monitor.load_all_measurements()
    
    # יצירת מנטר חדש
    new_monitor = StreamingPerformanceMonitor(performance_monitor.target_samples)
    
    # שמירת הנתונים הקיימים
    for measurement in current_data:
        new_monitor._save_measurement(measurement)
    
    # החלפה
    performance_monitor = new_monitor
    
    logging.info("🔬 Performance monitor upgraded to advanced streaming version")
    return new_monitor