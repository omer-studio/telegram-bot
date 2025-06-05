# =============================================
# bot_setup.py — התקנה והגדרה אוטומטית לסביבת פיתוח לוקאלית
# -------------------------------------------------------------
# קובץ זה מרכז את כל שלבי ההתקנה וההגדרה הראשוניים:
# 1. בדיקת venv והפעלה
# 2. התקנת כל התלויות (pip install ...)
# 3. בדיקת והרצת ngrok
# 4. איתור כתובת ngrok ועדכון webhook בטלגרם
# -------------------------------------------------------------
# הקובץ לא משנה כלום ב-Render, רק בסביבה לוקאלית.
# =============================================

import os
import subprocess
import sys
import time
import requests

# 1. בדיקת venv והפעלה
venv_path = os.path.join(os.getcwd(), 'venv')
if not os.path.exists(venv_path):
    print('🔧 יוצר venv חדש...')
    subprocess.run([sys.executable, '-m', 'venv', 'venv'])
else:
    print('✅ venv קיים')

# 2. התקנת כל התלויות
print('🔧 מתקין תלויות מ-requirements.txt...')
subprocess.run([os.path.join('venv', 'Scripts', 'python.exe'), '-m', 'pip', 'install', '--upgrade', 'pip'])
subprocess.run([os.path.join('venv', 'Scripts', 'python.exe'), '-m', 'pip', 'install', '-r', 'requirements.txt'])
subprocess.run([os.path.join('venv', 'Scripts', 'python.exe'), '-m', 'pip', 'install', 'uvicorn', 'requests'])

# 3. בדיקת והרצת ngrok
ngrok_path = os.path.join('ngrok-v3-stable-windows-amd64', 'ngrok.exe')
if not os.path.exists(ngrok_path):
    print('❌ לא נמצא ngrok.exe! יש להוריד ולהניח בתיקיה ngrok-v3-stable-windows-amd64')
    sys.exit(1)
else:
    print('✅ ngrok.exe קיים')

# בדוק אם ngrok כבר רץ
import psutil
ngrok_running = any('ngrok' in p.name().lower() for p in psutil.process_iter())
if not ngrok_running:
    print('🚀 מפעיל ngrok על פורט 10000...')
    subprocess.Popen([ngrok_path, 'http', '10000'])
    time.sleep(3)  # מחכה ש-ngrok יעלה
else:
    print('✅ ngrok כבר רץ')

# 4. איתור כתובת ngrok ועדכון webhook בטלגרם

def get_ngrok_public_url():
    try:
        resp = requests.get('http://127.0.0.1:4040/api/tunnels')
        tunnels = resp.json()['tunnels']
        for tunnel in tunnels:
            if tunnel['proto'] == 'https':
                return tunnel['public_url']
        for tunnel in tunnels:
            if tunnel['proto'] == 'http':
                return tunnel['public_url']
    except Exception as e:
        print('❌ לא הצלחתי לשלוף כתובת ngrok:', e)
    return None

# טען את הטוקן מה-config.json
import json
with open(os.path.join('etc', 'secrets', 'config.json'), encoding='utf-8') as f:
    config = json.load(f)
TELEGRAM_BOT_TOKEN = config['TELEGRAM_BOT_TOKEN']

ngrok_url = get_ngrok_public_url()
if not ngrok_url:
    print('❌ לא נמצאה כתובת ngrok פעילה! ודא ש-ngrok רץ.')
    sys.exit(1)
webhook_url = ngrok_url + '/webhook'
set_webhook_url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook?url={webhook_url}'
try:
    resp = requests.get(set_webhook_url)
    if resp.status_code == 200 and resp.json().get('ok'):
        print(f'✅ Webhook נקבע בטלגרם (אוטומטית לכתובת {webhook_url})!')
    else:
        print('⚠️ שגיאה בהגדרת Webhook:', resp.text)
except Exception as e:
    print('❌ שגיאה:', e)

print('\n✨ הכל מוכן! עכשיו תוכל להפעיל את השרת שלך כרגיל (uvicorn main:app_fastapi --host 0.0.0.0 --port 10000)') 