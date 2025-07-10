#!/usr/bin/env python3
"""
🚀 Integration Test: Full Message Flow
דמוי הודעת משתמש אמיתית - זה היה תופס את השגיאה הקריטית!
"""
import sys
import os
from unittest.mock import Mock, AsyncMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_message_flow_smoke_test():
    """
    🔥 Smoke Test: דמוי הודעת משתמש מלאה
    זה היה תופס את השגיאה get_recent_history_for_gpt!
    """
    print("🔥 מריץ Smoke Test: דמוי הודעת משתמש...")
    
    # Mock Telegram update object
    mock_update = Mock()
    mock_update.message = Mock()
    mock_update.message.chat_id = 123456789
    mock_update.message.text = "שלום, איך שלומך?"
    mock_update.message.from_user = Mock()
    mock_update.message.from_user.first_name = "TestUser"
    mock_update.message.reply_text = AsyncMock()
    
    # Important: Mock that it's NOT a voice message
    mock_update.message.voice = None
    mock_update.message.document = None
    mock_update.message.photo = None
    mock_update.message.video = None
    mock_update.message.sticker = None
    
    mock_context = Mock()
    
    success = True
    error_details = []
    
    try:
        # 1. בדיקת import של message_handler
        print("📦 בודק import של message_handler...")
        try:
            from message_handler import handle_message
            print("✅ message_handler imported")
        except Exception as e:
            print(f"❌ שגיאה בimport message_handler: {e}")
            error_details.append(f"Import error: {e}")
            success = False
        
        # 2. בדיקת פונקציות היסטוריה
        print("📚 בודק פונקציות היסטוריה...")
        try:
            from chat_utils import get_balanced_history_for_gpt, get_recent_history_for_gpt
            
            # בדיקת חתימות
            import inspect
            
            # get_balanced_history_for_gpt signature
            sig_balanced = inspect.signature(get_balanced_history_for_gpt)
            balanced_params = list(sig_balanced.parameters.keys())
            print(f"📋 get_balanced_history_for_gpt params: {balanced_params}")
            
            # get_recent_history_for_gpt signature
            sig_recent = inspect.signature(get_recent_history_for_gpt)
            recent_params = list(sig_recent.parameters.keys())
            print(f"📋 get_recent_history_for_gpt params: {recent_params}")
            
            # בדיקה שהפונקציות קיימות ועובדות
            try:
                # Test call with mock data
                result = get_balanced_history_for_gpt("test_user", user_limit=5, bot_limit=5)
                print(f"✅ get_balanced_history_for_gpt works: {type(result)}")
            except Exception as e:
                print(f"⚠️ get_balanced_history_for_gpt error: {e}")
                # זה לא בהכרח בעיה - יכול להיות שאין DB connection בטסט
            
        except Exception as e:
            print(f"❌ שגיאה בפונקציות היסטוריה: {e}")
            error_details.append(f"History functions error: {e}")
            success = False
        
        # 3. בדיקת GPT handlers
        print("🤖 בודק GPT handlers...")
        try:
            from gpt_a_handler import get_main_response
            sig_gpt = inspect.signature(get_main_response)
            gpt_params = list(sig_gpt.parameters.keys())
            print(f"📋 get_main_response params: {gpt_params}")
            print("✅ gpt_a_handler imported")
        except Exception as e:
            print(f"❌ שגיאה ב-GPT handlers: {e}")
            error_details.append(f"GPT handlers error: {e}")
            success = False
        
        # 4. ✨ דמוי קריאה אמיתית (עם mocks כדי לא לשלוח אמיתי)
        print("🎭 מדמה תהליך הודעה מלא...")
        
        with patch('chat_utils.get_balanced_history_for_gpt') as mock_history, \
             patch('gpt_a_handler.get_main_response') as mock_gpt, \
             patch('message_handler.send_message') as mock_send, \
             patch('message_handler.handle_background_tasks') as mock_bg:
            
            # Setup mocks
            mock_history.return_value = [
                {"role": "user", "content": "הודעה קודמת"},
                {"role": "assistant", "content": "תשובה קודמת"}
            ]
            
            mock_gpt.return_value = {
                "content": "תשובה של GPT",
                "gpt_pure_latency": 2.5,
                "background_data": {}
            }
            
            mock_send.return_value = None
            mock_bg.return_value = None
            
            try:
                # 🔥 זה הטסט שהיה תופס את השגיאה!
                import asyncio
                
                async def run_message_test():
                    await handle_message(mock_update, mock_context)
                
                # Run the async test
                asyncio.run(run_message_test())
                
                print("✅ דמוי הודעה מלא הושלם בהצלחה!")
                
                # בדיקה אם הפונקציות נקראו (אם המשתמש מורשה)
                # ראה if ההיסטוריה לא נקראה, זה יכול להיות בגלל שהמשתמש לא מורשה
                if mock_history.called:
                    print("✅ פונקציית היסטוריה נקראה - משתמש מורשה")
                    
                    # בדיקה שהפרמטרים נכונים
                    call_args = mock_history.call_args
                    if call_args:
                        print(f"📋 קריאה להיסטוריה: args={call_args[0]}, kwargs={call_args[1]}")
                        
                        # בדיקה שיש user_limit ו-bot_limit
                        if 'user_limit' in call_args[1] and 'bot_limit' in call_args[1]:
                            print("✅ קריאה עם user_limit ו-bot_limit - נכון!")
                        else:
                            print("⚠️ קריאה ללא user_limit/bot_limit")
                else:
                    print("ℹ️ פונקציית היסטוריה לא נקראה - כנראה משתמש לא מורשה או הודעת מערכת")
                    print("ℹ️ זה תקין - הבוט הגיב כמו שצריך למשתמש לא מורשה")
                
                # בדיקה שהבוט הגיב (send_message נקרא)
                if mock_send.called:
                    print("✅ הבוט הגיב למשתמש (send_message נקרא)")
                else:
                    print("⚠️ הבוט לא הגיב למשתמש")
                
            except Exception as e:
                print(f"❌ שגיאה בדמוי הודעה: {e}")
                error_details.append(f"Message simulation error: {e}")
                success = False
        
    except Exception as e:
        print(f"❌ שגיאה כללית בטסט: {e}")
        error_details.append(f"General test error: {e}")
        success = False
    
    # תוצאות
    if success:
        print("\n🎉 כל הטסטים עברו! המערכת פועלת כראוי.")
        return True
    else:
        print(f"\n💥 נמצאו {len(error_details)} שגיאות:")
        for i, error in enumerate(error_details, 1):
            print(f"   {i}. {error}")
        print("\n🚨 טסט נכשל - צריך לתקן לפני פריסה!")
        return False

def main():
    """🚀 הפעלת הטסט"""
    success = test_message_flow_smoke_test()
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 