#!/usr/bin/env python3
import json
import requests

print('🔍 בודק נתוני API של רנדר...')

try:
    with open('etc/secrets/config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    api_key = config.get('RENDER_API_KEY')
    service_id = config.get('RENDER_SERVICE_ID')
    
    print(f'📋 Service ID: {service_id[:10] if service_id else "לא נמצא"}...')
    print(f'🔑 API Key: {"יש" if api_key else "לא נמצא"}')
    
    if api_key:
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json'
        }
        
        print('\n🔍 בודק גישה לרנדר...')
        response = requests.get('https://api.render.com/v1/services', headers=headers, timeout=10)
        
        if response.status_code == 200:
            services = response.json()
            print(f'✅ גישה תקינה! נמצאו {len(services)} שירותים')
            
            for service in services:
                name = service.get('name', '')
                sid = service.get('id', '')
                print(f'   📦 {name}: {sid}')
        else:
            print(f'❌ שגיאה בגישה: {response.status_code}')
            print(f'   📄 תגובה: {response.text}')
            
except Exception as e:
    print(f'❌ שגיאה: {e}') 