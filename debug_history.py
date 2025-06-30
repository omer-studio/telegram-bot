import json
import sys
import os

# הוספת הנתיב לפרויקט
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chat_utils import get_chat_history_messages

# קריאת ההיסטוריה
with open('data/chat_history.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

history = data['111709341']['history']
print(f'Total entries: {len(history)}')

# בדיקת רשומות עם תוכן
user_entries = [e for e in history if e.get('user', '').strip()]
bot_entries = [e for e in history if e.get('bot', '').strip()]

print(f'Entries with user content: {len(user_entries)}')
print(f'Entries with bot content: {len(bot_entries)}')

# הדפסת 4 הרשומות האחרונות
print('\nLast 4 entries:')
for i, entry in enumerate(history[-4:]):
    user = entry.get('user', '')
    bot = entry.get('bot', '')
    print(f'  {i}: user="{user}" bot="{bot[:50]}{"..." if len(bot) > 50 else ""}"')

# שימוש בפונקציה האמיתית
print('\nUsing REAL get_chat_history_messages:')
messages = get_chat_history_messages('111709341', limit=15)  # 🔧 הגבלה ל-15 הודעות
user_count = len([m for m in messages if m['role'] == 'user'])
assistant_count = len([m for m in messages if m['role'] == 'assistant'])

print(f'Messages sent to GPT: {len(messages)} (user={user_count}, assistant={assistant_count})')

# הדפסת ההודעות האחרונות
print('\nLast 4 messages sent to GPT:')
for i, msg in enumerate(messages[-4:]):
    content = msg['content'][:50] + "..." if len(msg['content']) > 50 else msg['content']
    print(f'  {i}: {msg["role"]}="{content}"') 