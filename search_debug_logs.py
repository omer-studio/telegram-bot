#!/usr/bin/env python3
"""
חיפוש הודעות דיבאג ספציפיות בלוגי רנדר
"""
import requests
import json
import os
from datetime import datetime, timezone

def search_debug_in_render_logs():
    """חיפוש הודעות הדיבאג שהוספתי בלוגי רנדר"""
    
    try:
        # טעינת הגדרות
        config_path = os.path.join("etc", "secrets", "config.json")
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        api_key = config.get("RENDER_API_KEY")
        service_id = config.get("RENDER_SERVICE_ID")
        
        if not api_key or not service_id:
            print("❌ חסרים מפתח API או Service ID")
            return
        
        print("🔍 מחפש הודעות דיבאג בלוגי רנדר...")
        
        # בקשת לוגים אחרונים
        headers = {"Authorization": f"Bearer {api_key}"}
        url = f"https://api.render.com/v1/services/{service_id}/logs"
        
        params = {
            "limit": 1000,  # הרבה לוגים
            "cursor": "",
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"❌ שגיאה בבקשת לוגים: {response.status_code}")
            return
        
        logs_data = response.json()
        logs = logs_data.get("data", [])
        
        print(f"📋 נטענו {len(logs)} לוגים, מחפש הודעות דיבאג...")
        
        # חיפוש הודעות דיבאג ספציפיות
        debug_keywords = [
            "[DEBUG] מתחיל טעינת נתונים",
            "[DEBUG] מייבא get_chat_history_messages_fast", 
            "[DEBUG] קורא להיסטוריה עבור",
            "[DEBUG] היסטוריה הוחזרה:",
            "[HISTORY_DEBUG] שגיאה בטעינת נתונים",
            "[HISTORY_DEBUG] exception type:",
            "[HISTORY_DEBUG] full traceback:",
            "🔧 [DEBUG]",
            "🚨 [HISTORY_DEBUG]"
        ]
        
        found_debug = []
        recent_logs = []
        
        for log in logs:
            timestamp = log.get("timestamp", "")
            message = log.get("message", "")
            
            # התמקדות בלוגים מ-17:53 ואילך (זמן ההודעות החדשות)
            if "2025-07-08T17:53" in timestamp or "2025-07-08T17:54" in timestamp:
                recent_logs.append((timestamp, message))
                
                # חיפוש הודעות דיבאג
                for keyword in debug_keywords:
                    if keyword in message:
                        found_debug.append((timestamp, message))
                        break
        
        print(f"\n📊 נמצאו {len(recent_logs)} לוגים מ-17:53 ואילך")
        print(f"🔍 נמצאו {len(found_debug)} הודעות דיבאג!")
        
        if found_debug:
            print(f"\n🎯 הודעות דיבאג שנמצאו:")
            for i, (ts, msg) in enumerate(found_debug, 1):
                print(f"   {i}. {ts}")
                print(f"      {msg}")
                print()
        else:
            print(f"\n⚠️ לא נמצאו הודעות דיבאג!")
            print(f"🔍 בואו נראה דוגמא מהלוגים האחרונים:")
            
            for i, (ts, msg) in enumerate(recent_logs[-10:], 1):
                if len(msg.strip()) > 10:  # רק הודעות משמעותיות
                    print(f"   {i}. {ts}: {msg[:100]}{'...' if len(msg) > 100 else ''}")
        
        # חיפוש הודעות שגיאה כלליות
        error_logs = []
        for ts, msg in recent_logs:
            if any(word in msg.lower() for word in ['error', 'exception', 'traceback', 'failed', 'שגיאה']):
                error_logs.append((ts, msg))
        
        if error_logs:
            print(f"\n🚨 הודעות שגיאה אחרונות:")
            for i, (ts, msg) in enumerate(error_logs[-5:], 1):
                print(f"   {i}. {ts}: {msg}")
        
    except Exception as e:
        print(f"❌ שגיאה בחיפוש לוגים: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    search_debug_in_render_logs() 