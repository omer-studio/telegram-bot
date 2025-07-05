import json
from datetime import datetime, timedelta
import pytz

def check_log_for_date(target_date):
    tz = pytz.timezone('Europe/Berlin')
    target_date = datetime.now(tz).date() - timedelta(days=1)
    print(f'Looking for interactions on: {target_date}')
    
    interactions = 0
    with open('data/gpt_usage_log.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get('timestamp', '').startswith(str(target_date)):
                    interactions += 1
            except:
                continue
    
    print(f'Found {interactions} interactions for {target_date}')
    
    # בדיקה של התאריכים האחרונים בקובץ
    print("\nLast 5 entries in log:")
    with open('data/gpt_usage_log.jsonl', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line in lines[-5:]:
            try:
                entry = json.loads(line)
                print(f"  {entry.get('timestamp', 'N/A')}")
            except:
                continue

if __name__ == "__main__":
    check_log_for_date(None) 