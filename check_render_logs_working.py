#!/usr/bin/env python3
"""
🔍 בדיקת תפקוד מערכת שיקוף לוגי Render
בודק שהלוגים מהרנדר נשמרים במסד הנתונים
"""

import os
import json
from datetime import datetime, timedelta
import time

def get_config():
    """טעינת קונפיגורציה"""
    try:
        from config import get_config
        return get_config()
    except:
        config_path = "etc/secrets/config.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

def check_database_logs():
    """בדיקת לוגים במסד הנתונים"""
    try:
        import psycopg2
        config = get_config()
        db_url = config.get("DATABASE_EXTERNAL_URL") or config.get("DATABASE_URL")
        
        if not db_url:
            print("❌ לא נמצא DB_URL")
            return False
            
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        # בדיקה כמה לוגים יש סה"כ
        cur.execute("SELECT COUNT(*) FROM deployment_logs;")
        total_logs = cur.fetchone()[0]
        print(f"📊 סה\"כ לוגים במסד: {total_logs}")
        
        # בדיקה כמה לוגים מהשעה האחרונה
        cur.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE created_at >= NOW() - INTERVAL '1 hour';
        """)
        recent_logs = cur.fetchone()[0]
        print(f"🕐 לוגים מהשעה האחרונה: {recent_logs}")
        
        # בדיקה כמה לוגים מ-render_api_mirror
        cur.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE source_module LIKE '%render%' OR message LIKE '%render%' OR source_module = 'render_logs_mirror';
        """)
        render_logs = cur.fetchone()[0]
        print(f"🔥 לוגים מ-Render API: {render_logs}")
        
        # דוגמאות לוגים אחרונים
        cur.execute("""
            SELECT created_at, source_module, LEFT(message, 100) as message_preview
            FROM deployment_logs 
            ORDER BY created_at DESC 
            LIMIT 10;
        """)
        latest_logs = cur.fetchall()
        
        print(f"\n📋 10 הלוגים האחרונים:")
        for log in latest_logs:
            print(f"  {log[0]} | {log[1]} | {log[2]}")
        
        # בדיקה ספציפית ללוגים מהרנדר הלייב
        cur.execute("""
            SELECT COUNT(*) FROM deployment_logs 
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            AND (message LIKE '%LiteLLM%' OR message LIKE '%HTTP Request%' OR message LIKE '%GPT%');
        """)
        live_render_logs = cur.fetchone()[0]
        print(f"🎯 לוגים מתקדמים (LiteLLM/HTTP/GPT) מ-10 דקות אחרונות: {live_render_logs}")
        
        cur.close()
        conn.close()
        
        return {
            "total_logs": total_logs,
            "recent_logs": recent_logs,
            "render_logs": render_logs,
            "live_render_logs": live_render_logs
        }
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת מסד נתונים: {e}")
        return None

def check_render_api_config():
    """בדיקת הגדרות Render API"""
    try:
        config = get_config()
        api_key = config.get("RENDER_API_KEY", "")
        service_id = config.get("RENDER_SERVICE_ID", "")
        
        print(f"🔑 Render API Key: {'✅ קיים' if api_key else '❌ חסר'}")
        print(f"🆔 Render Service ID: {'✅ קיים' if service_id else '❌ חסר'}")
        
        if api_key:
            print(f"   Key prefix: {api_key[:8]}...")
        if service_id:
            print(f"   Service ID: {service_id}")
            
        return bool(api_key and service_id)
        
    except Exception as e:
        print(f"❌ שגיאה בבדיקת קונפיגורציה: {e}")
        return False

def main():
    """פונקציה ראשית"""
    print("🔍 בדיקת מערכת שיקוף לוגי Render")
    print("=" * 50)
    
    # בדיקת קונפיגורציה
    print("\n📋 בדיקת קונפיגורציה:")
    config_ok = check_render_api_config()
    
    # בדיקת מסד נתונים
    print("\n📊 בדיקת מסד נתונים:")
    db_results = check_database_logs()
    
    # סיכום
    print("\n" + "=" * 50)
    print("📝 סיכום:")
    
    if not config_ok:
        print("❌ קונפיגורציה: בעיה במפתחות Render")
    else:
        print("✅ קונפיגורציה: תקינה")
    
    if not db_results:
        print("❌ מסד נתונים: לא ניתן לגשת")
    else:
        if db_results["live_render_logs"] > 0:
            print("✅ שיקוף לוגים: פועל בהצלחה!")
            print(f"   🎯 {db_results['live_render_logs']} לוגים מתקדמים נשמרו")
        elif db_results["render_logs"] > 0:
            print("⚠️ שיקוף לוגים: חלקי (יש לוגים ישנים)")
        else:
            print("❌ שיקוף לוגים: לא פועל")
    
    print("\n🚀 אם הכל תקין, תשלח הודעה לבוט ותבדוק שוב!")

if __name__ == "__main__":
    main() 