#!/usr/bin/env python3

def test_new_fix():
    print('🧪 בדיקת התיקון החדש...')
    
    try:
        from chat_utils import get_chat_history_messages_fast
        print('✅ יבוא chat_utils הצליח')
        
        # בדיקה עם integer chat_id
        print(f'🔍 בודק היסטוריה עבור chat_id=111709341...')
        history = get_chat_history_messages_fast(111709341, 5)
        print(f'📋 קיבלתי {len(history)} הודעות')
        
        if len(history) > 0:
            print('✅ ההיסטוריה נטענה בהצלחה!')
            for i, msg in enumerate(history[:3]):
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:50]
                print(f'   {i+1}. {role}: "{content}..."')
        else:
            print('⚠️ לא נמצאו הודעות (זה יכול להיות תקין)')
        
    except Exception as e:
        print(f'❌ שגיאה: {e}')
        import traceback
        traceback.print_exc()
    
    try:
        from profile_utils import get_user_summary_fast
        print('\n🔍 בודק סיכום משתמש...')
        summary = get_user_summary_fast(111709341)
        print(f'📝 סיכום: "{summary}"')
        
    except Exception as e:
        print(f'❌ שגיאה בסיכום: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_new_fix() 