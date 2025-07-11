#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from simple_data_manager import SimpleDataManager
import simple_config as config

print("🔍 בודק מסד נתונים...")
print(f"✅ URL קיים: {bool(config.get_db_url())}")

dm = SimpleDataManager()

try:
    result = dm.execute_query("SELECT COUNT(*) as count FROM chat_messages", fetch_one=True)
    if result:
        print(f"📊 chat_messages: {result[0]} רשומות")
    else:
        print("❌ אין תוצאות")
except Exception as e:
    print(f"❌ שגיאה: {e}")

try:
    result = dm.execute_query("SELECT COUNT(*) as count FROM user_profiles", fetch_one=True)
    if result:
        print(f"👤 user_profiles: {result[0]} רשומות")
    else:
        print("❌ אין תוצאות ב-user_profiles")
except Exception as e:
    print(f"❌ שגיאה ב-user_profiles: {e}") 