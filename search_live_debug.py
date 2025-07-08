#!/usr/bin/env python3
"""
סקריפט לחיפוש הודעות דיבאג בלוגי רנדר החיים
"""
import requests
import json
import sys
import os
from datetime import datetime, timedelta

def fetch_render_logs():
    """משיכת לוגים חיים מרנדר"""
    
    # קריאת קונפיגורציה
    with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    api_key = config.get('RENDER_API_KEY')
    service_id = config.get('RENDER_SERVICE_ID')
    
    if not api_key or not service_id:
        print("❌ חסרים נתוני API של רנדר")
        return []
    
    # URL ללוגים
    url = f"https://api.render.com/v1/services/{service_id}/logs"
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    # זמן התחלה - 30 דקות אחורה
    start_time = datetime.utcnow() - timedelta(minutes=30)
    
    params = {
        'startTime': start_time.isoformat() + 'Z',
        'limit': 1000  # מקסימום לוגים
    }
    
    try:
        print(f"🔍 משיכת לוגים מרנדר מ-{start_time.strftime('%H:%M')}...")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        logs_data = response.json()
        return logs_data.get('logs', [])
        
    except Exception as e:
        print(f"❌ שגיאה במשיכת לוגים: {e}")
        return []

def search_debug_messages(logs):
    """חיפוש הודעות דיבאג ברשימת לוגים"""
    
    debug_keywords = [
        'DEBUG',
        'HISTORY_DEBUG', 
        'מתחיל טעינת נתונים',
        'שגיאה בטעינת נתונים',
        'מנסה להשיג היסטוריה',
        'Exception.*data_err'
    ]
    
    found_debug = []
    
    for log_entry in logs:
        message = log_entry.get('message', '')
        timestamp = log_entry.get('timestamp', '')
        
        for keyword in debug_keywords:
            if keyword in message:
                found_debug.append({
                    'timestamp': timestamp,
                    'keyword': keyword, 
                    'message': message
                })
                break
    
    return found_debug

def main():
    print("🚀 חיפוש דיבאג בלוגי רנדר החיים")
    print("=" * 50)
    
    # משיכת לוגים
    logs = fetch_render_logs()
    
    if not logs:
        print("❌ לא נמצאו לוגים")
        return
    
    print(f"📋 נמצאו {len(logs)} לוגים")
    
    # חיפוש דיבאג
    debug_messages = search_debug_messages(logs)
    
    if debug_messages:
        print(f"\n🔧 נמצאו {len(debug_messages)} הודעות דיבאג:")
        print("-" * 50)
        
        for debug in debug_messages:
            timestamp = debug['timestamp']
            keyword = debug['keyword']
            message = debug['message']
            
            print(f"🕐 {timestamp}")
            print(f"🔑 מילת מפתח: {keyword}")
            print(f"💬 הודעה: {message}")
            print("-" * 30)
    else:
        print("\n⚠️ לא נמצאו הודעות דיבאג")
        
        # הצגת דוגמאות לוגים
        print("\n📝 דוגמאות לוגים אחרונים:")
        for log_entry in logs[-10:]:  # 10 אחרונים
            timestamp = log_entry.get('timestamp', '')
            message = log_entry.get('message', '')[:100]
            print(f"   {timestamp}: {message}...")

if __name__ == "__main__":
    main() 