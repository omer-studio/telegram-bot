
# 🚨 הגנה מפני מחיקות chat_messages
CHAT_MESSAGES_DELETE_DISABLED = True

def protect_chat_messages():
    """מונע מחיקת chat_messages"""
    if CHAT_MESSAGES_DELETE_DISABLED:
        raise Exception("🚨 BLOCKED: מחיקת chat_messages חסומה לחלוטין!")
