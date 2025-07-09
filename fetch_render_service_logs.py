#!/usr/bin/env python3
"""
חיפוש לוגי אפליקציה ברנדר דרך API
"""
import requests
import json
from datetime import datetime, timedelta

def fetch_service_logs():
    """משיכת לוגי השירות מרנדר"""
    
    print('🔍 חיפוש לוגי השירות ברנדר...')
    
    try:
        # 🔧 תיקון מערכתי: שימוש ב-get_config() מרכזי במקום קריאה קשיחה
        from config import get_config
        config = get_config()
    except Exception as e:
        print(f'❌ שגיאה בקריאת קונפיגורציה: {e}')
        return

    api_key = config.get('RENDER_API_KEY')
    service_id = config.get('RENDER_SERVICE_ID')
    
    if not api_key or not service_id:
        print("❌ חסרים נתוני API של רנדר")
        return

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json'
    }
    
    # 1. קודם בואו נבדוק איזה שירות יש לנו
    print(f'📋 בודק שירות: {service_id}')
    
    try:
        # מידע על השירות
        service_url = f"https://api.render.com/v1/services/{service_id}"
        from simple_config import TimeoutConfig
        service_response = requests.get(service_url, headers=headers, timeout=TimeoutConfig.RENDER_API_TIMEOUT)
        
        if service_response.status_code == 200:
            service_data = service_response.json()
            print(f'✅ שירות נמצא: {service_data.get("name", "ללא שם")}')
            print(f'   📊 סטטוס: {service_data.get("serviceDetails", {}).get("status", "לא ידוע")}')
        else:
            print(f'❌ שגיאה בגישה לשירות: {service_response.status_code}')
            print(f'   📄 תגובה: {service_response.text}')
            return
            
    except Exception as e:
        print(f'❌ שגיאה בבדיקת שירות: {e}')
        return

    # 2. עכשיו בואו ננסה לקבל לוגים
    print('\n🔍 משיכת לוגי השירות...')
    
    # זמן התחלה - שעה אחרונה
    start_time = datetime.utcnow() - timedelta(hours=1)
    
    try:
        # URL ללוגים  
        logs_url = f"https://api.render.com/v1/services/{service_id}/logs"
        
        params = {
            'startTime': start_time.isoformat() + 'Z',
            'limit': 1000
        }
        
        logs_response = requests.get(logs_url, headers=headers, params=params, timeout=TimeoutConfig.RENDER_LOGS_TIMEOUT)
        
        if logs_response.status_code == 200:
            logs_data = logs_response.json()
            logs = logs_data.get('logs', [])
            
            print(f'📋 נמצאו {len(logs)} לוגים')
            
            if logs:
                print('\n📝 לוגים אחרונים:')
                for log_entry in logs[-20:]:  # 20 אחרונים
                    timestamp = log_entry.get('timestamp', '')
                    message = log_entry.get('message', '')
                    level = log_entry.get('level', 'INFO')
                    
                    print(f'   [{level}] {timestamp}: {message[:100]}...')
                
                # חיפוש דיבאג ספציפי
                debug_keywords = [
                    'DEBUG',
                    'HISTORY_DEBUG', 
                    'מתחיל טעינת נתונים',
                    'שגיאה בטעינת נתונים'
                ]
                
                print('\n🔧 חיפוש הודעות דיבאג:')
                found_debug = False
                
                for log_entry in logs:
                    message = log_entry.get('message', '')
                    timestamp = log_entry.get('timestamp', '')
                    
                    for keyword in debug_keywords:
                        if keyword in message:
                            found_debug = True
                            print(f'🎯 נמצא "{keyword}":')
                            print(f'   📅 {timestamp}')
                            print(f'   💬 {message}')
                            print('-' * 50)
                            break
                
                if not found_debug:
                    print('⚠️ לא נמצאו הודעות דיבאג')
                    
                    # נראה אם יש print statements כלליים
                    print('\n📋 דוגמאות לוגים עם "chat_id":')
                    for log_entry in logs:
                        message = log_entry.get('message', '')
                        if 'chat_id' in message:
                            timestamp = log_entry.get('timestamp', '')
                            print(f'   {timestamp}: {message[:80]}...')
                            
            else:
                print('📭 אין לוגים בשעה האחרונה')
                
        else:
            print(f'❌ שגיאה בקבלת לוגים: {logs_response.status_code}')
            print(f'   📄 תגובה: {logs_response.text}')
            
    except Exception as e:
        print(f'❌ שגיאה במשיכת לוגים: {e}')

if __name__ == "__main__":
    fetch_service_logs() 