#!/usr/bin/env python3
"""
🔍 MCP Database Tool - כלי לשאילתות read-only למסד הנתונים
מאפשר ל-Cursor Chat לבצע SELECT queries ישירות במסד הנתונים לצורך ניתוח

Usage from Cursor Chat:
@run_query("SELECT chat_id, code_try FROM user_profiles WHERE code_try>0 LIMIT 5")
"""

import os
import re
import json
import traceback
from typing import List, Dict, Any

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    print("⚠️ psycopg2 not available - database queries disabled")
    PSYCOPG2_AVAILABLE = False

def load_config():
    """🎯 טעינת קונפיגורציה דרך הפונקציה המרכזית"""
    try:
        from config import get_config
        return get_config()
    except Exception as e:
        print(f"❌ שגיאה בטעינת קונפיגורציה: {e}")
        return {}

def get_database_url():
    """קבלת URL למסד הנתונים מהקונפיגורציה הקיימת"""
    config = load_config()
    if not config:
        return None
    
    # שימוש באותו דפוס כמו בקוד הקיים
    return config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")

def run_query(query: str) -> List[Dict[str, Any]]:
    """
    Execute a read-only SQL SELECT on the production Postgres
    
    Args:
        query (str): SQL SELECT query to execute
        
    Returns:
        List[Dict[str, Any]]: Query results as list of dictionaries
        
    Raises:
        ValueError: If query is not a SELECT statement
        Exception: If database connection or query execution fails
    """
    if not PSYCOPG2_AVAILABLE:
        return [{"error": "psycopg2 not available - cannot execute database queries"}]
    
    # 🔒 אבטחה: רק שאילתות SELECT מותרות
    if not re.match(r'^\s*select', query.strip(), re.IGNORECASE):
        raise ValueError("❌ Only SELECT queries are allowed. Query must start with SELECT.")
    
    # חסימת פקודות מסוכנות - בדיקה על גבולות מילים
    dangerous_keywords = [
        'insert', 'update', 'delete', 'drop', 'create', 'alter', 
        'truncate', 'grant', 'revoke', 'exec', 'execute'
    ]
    
    query_lower = query.lower()
    for keyword in dangerous_keywords:
        # בדיקה שהמילה מופיעה כמילה שלמה ולא כחלק ממילה אחרת
        if re.search(r'\b' + keyword + r'\b', query_lower):
            raise ValueError(f"❌ Dangerous keyword '{keyword}' detected in query. Only SELECT queries allowed.")
    
    try:
        db_url = get_database_url()
        if not db_url:
            return [{"error": "❌ DATABASE_URL not found in configuration"}]
        
        print(f"🔍 Executing query: {query[:100]}{'...' if len(query) > 100 else ''}")
        
        # חיבור למסד הנתונים עם הגדרת SSL
        conn = psycopg2.connect(db_url, sslmode="require")
        
        # שימוש ב-RealDictCursor כדי לקבל תוצאות כ-dictionaries
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # הרצת השאילתה
        cur.execute(query)
        
        # קבלת התוצאות
        rows = cur.fetchall()
        
        # סגירת החיבורים
        cur.close()
        conn.close()
        
        # המרה לרשימת dictionaries (JSON serializable)
        results = [dict(row) for row in rows]
        
        print(f"✅ Query executed successfully. Returned {len(results)} rows")
        
        return results
        
    except psycopg2.Error as db_error:
        error_msg = f"❌ Database error: {str(db_error)}"
        print(error_msg)
        return [{"error": error_msg, "type": "database_error"}]
        
    except Exception as e:
        error_msg = f"❌ Unexpected error: {str(e)}"
        print(error_msg)
        print(f"🔍 Traceback: {traceback.format_exc()}")
        return [{"error": error_msg, "type": "unexpected_error"}]

# פונקציות נוספות לשימוש נוח
def query_user_profiles(limit: int = 10) -> List[Dict[str, Any]]:
    """שאילתה מהירה לטבלת user_profiles"""
    query = f"SELECT * FROM user_profiles ORDER BY updated_at DESC LIMIT {limit}"
    return run_query(query)

def query_recent_messages(limit: int = 10) -> List[Dict[str, Any]]:
    """שאילתה מהירה להודעות אחרונות - רק שדות קיימים"""
    query = f"SELECT id, chat_id, user_msg, bot_msg, timestamp FROM chat_messages ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def query_table_info(table_name: str) -> List[Dict[str, Any]]:
    """מידע על מבנה טבלה"""
    query = f"""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns 
    WHERE table_name = '{table_name}'
    ORDER BY ordinal_position
    """
    return run_query(query)

# 🎯 פונקציות טבלאות מלאות בעברית
def טבלה_משתמשים(limit: int = 20) -> List[Dict[str, Any]]:
    """הצגת טבלת user_profiles מלאה עם כל השדות"""
    query = f"SELECT * FROM user_profiles ORDER BY updated_at DESC LIMIT {limit}"
    return run_query(query)

def טבלה_הודעות(limit: int = 30) -> List[Dict[str, Any]]:
    """הצגת טבלת chat_messages מלאה עם כל השדות הקיימים"""
    query = f"SELECT id, chat_id, user_msg, bot_msg, timestamp FROM chat_messages ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_הודעות_משתמש(chat_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """הצגת הודעות של משתמש ספציפי מלאות - רק שדות קיימים"""
    query = f"SELECT id, chat_id, user_msg, bot_msg, timestamp FROM chat_messages WHERE chat_id = '{chat_id}' ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_gpt_לוגים(limit: int = 25) -> List[Dict[str, Any]]:
    """🔥 הצגת טבלת interactions_log החדשה עם נתונים מתקדמים"""
    query = f"SELECT * FROM interactions_log ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_gpt_קריאות(limit: int = 25) -> List[Dict[str, Any]]:
    """הצגת טבלת gpt_calls מלאה עם כל השדות"""
    query = f"SELECT * FROM gpt_calls ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_שגיאות(limit: int = 20) -> List[Dict[str, Any]]:
    """הצגת טבלת errors_stats מלאה עם כל השדות"""
    query = f"SELECT * FROM errors_stats ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_פריסות(limit: int = 15) -> List[Dict[str, Any]]:
    """הצגת טבלת deployment_logs מלאה עם כל השדות"""
    query = f"SELECT * FROM deployment_logs ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_משתמשים_קריטיים(limit: int = 15) -> List[Dict[str, Any]]:
    """הצגת טבלת critical_users מלאה עם כל השדות"""
    query = f"SELECT * FROM critical_users ORDER BY updated_at DESC LIMIT {limit}"
    return run_query(query)

def טבלה_חיובים(limit: int = 20) -> List[Dict[str, Any]]:
    """הצגת טבלת billing_usage מלאה עם כל השדות"""
    query = f"SELECT * FROM billing_usage ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_מגבלות_חינמיות(limit: int = 15) -> List[Dict[str, Any]]:
    """הצגת טבלת free_model_limits מלאה עם כל השדות"""
    query = f"SELECT * FROM free_model_limits ORDER BY updated_at DESC LIMIT {limit}"
    return run_query(query)

def טבלה_gpt_שימוש(limit: int = 20) -> List[Dict[str, Any]]:
    """הצגת טבלת gpt_usage_log מלאה עם כל השדות"""
    query = f"SELECT * FROM gpt_usage_log ORDER BY timestamp DESC LIMIT {limit}"
    return run_query(query)

def טבלה_מפורטת(table_name: str, limit: int = 20) -> List[Dict[str, Any]]:
    """הצגת כל טבלה לפי שם עם כל השדות"""
    query = f"SELECT * FROM {table_name} LIMIT {limit}"
    return run_query(query)

def חיפוש_משתמש_מלא(chat_id: str) -> Dict[str, Any]:
    """🔥 חיפוש מידע מלא על משתמש ספציפי - כל הטבלאות (עודכן ל-interactions_log)"""
    user_profile = run_query(f"SELECT * FROM user_profiles WHERE chat_id = '{chat_id}'")
    recent_messages = run_query(f"SELECT id, chat_id, user_msg, bot_msg, timestamp FROM chat_messages WHERE chat_id = '{chat_id}' ORDER BY timestamp DESC LIMIT 10")
    gpt_interactions = run_query(f"SELECT * FROM interactions_log WHERE chat_id = '{chat_id}' ORDER BY timestamp DESC LIMIT 10")
    
    return {
        "פרופיל_מלא": user_profile,
        "הודעות_מלאות": recent_messages,
        "אינטראקציות_מלאות": gpt_interactions
    }

def סטטיסטיקות_כלליות() -> Dict[str, Any]:
    """🔥 סטטיסטיקות כלליות של המערכת (עודכן ל-interactions_log)"""
    total_users = run_query("SELECT COUNT(*) as total FROM user_profiles")[0]['total']
    approved_users = run_query("SELECT COUNT(*) as approved FROM user_profiles WHERE approved = true")[0]['approved']
    messages_today = run_query("SELECT COUNT(*) as today FROM chat_messages WHERE DATE(timestamp) = CURRENT_DATE")[0]['today']
    # חישוב עלות מ-interactions_log (אגורות מומרות לדולרים)
    cost_week_agorot = run_query("SELECT COALESCE(SUM(total_cost_agorot), 0) as week_cost FROM interactions_log WHERE timestamp >= NOW() - INTERVAL '7 days'")[0]['week_cost']
    cost_week_usd = float(cost_week_agorot) / 100 / 3.7 if cost_week_agorot else 0  # 1 אגורה = 0.01 שקל, 1 שקל ≈ 0.27 דולר
    
    return {
        "סה_כ_משתמשים": total_users,
        "משתמשים_מאושרים": approved_users,
        "הודעות_היום": messages_today,
        "עלות_שבוע_דולר": round(cost_week_usd, 4)
    }

# פונקציה למתודולוגיות debug
def test_connection() -> Dict[str, Any]:
    """בדיקת חיבור למסד הנתונים"""
    try:
        result = run_query("SELECT NOW() as current_time, version() as pg_version")
        if result and not result[0].get("error"):
            return {
                "status": "✅ Connected successfully",
                "connection_test": result[0]
            }
        else:
            return {
                "status": "❌ Connection failed", 
                "error": result[0].get("error") if result else "Unknown error"
            }
    except Exception as e:
        return {
            "status": "❌ Connection test failed",
            "error": str(e)
        }

if __name__ == "__main__":
    # בדיקה מקומית של הכלי
    print("🧪 Testing database tool...")
    
    # בדיקת חיבור
    connection_test = test_connection()
    print(f"Connection test: {connection_test}")
    
    # בדיקת שאילתה פשוטה
    try:
        result = run_query("SELECT COUNT(*) as total_users FROM user_profiles")
        print(f"Sample query result: {result}")
    except Exception as e:
        print(f"Sample query failed: {e}") 