from db_manager import create_tables, save_chat_message, get_chat_history
from datetime import datetime

print('🔧 יוצר טבלאות (אם צריך)...')
create_tables()

print('📝 מנסה לשמור הודעת צ\'אט לדוגמה...')
chat_id = 'test_123'
user_msg = 'שלום, בדיקת מערכת!'
bot_msg = 'שלום! הכל עובד.'
timestamp = datetime.utcnow()
save_chat_message(chat_id, user_msg, bot_msg, timestamp)
print('✅ נשמרה הודעה לדוגמה.')

print('🔍 מנסה לשלוף היסטוריית צ\'אט...')
history = get_chat_history(chat_id, limit=10)
print('📋 תוצאה:')
for row in history:
    print(row) 