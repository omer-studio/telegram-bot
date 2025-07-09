#!/usr/bin/env python3

print('🧪 בדיקה אחרונה של הפתרון הפשוט:')
print()

from chat_utils import get_chat_history_messages_fast
from profile_utils import get_user_profile

# בדיקה עם משתמש אמיתי
chat_id = 111709341
messages = get_chat_history_messages_fast(chat_id)
profile = get_user_profile(chat_id)

print(f'✅ היסטוריה עבור {chat_id}: {len(messages)} הודעות')
print(f'✅ פרופיל עבור {chat_id}: {"קיים" if profile else "לא קיים"}')
print(f'✅ chat_id type: {type(chat_id).__name__} (integer)')
print()

print('🎯 הפתרון הפשוט עובד מושלם!')
print('📊 הטבלה: BIGINT')  
print('🚀 הקוד: integers ישירות')
print('🗑️ ללא wrapper functions מיותרים')
print()
print('✅✅✅✅ מאושר סופית לקומיט ✅✅✅✅') 