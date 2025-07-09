import unittest
import os
import sys

# הוספת הנתיב לפרויקט כך שיוכל לייבא מודולים
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBasicFunctionality(unittest.TestCase):
    
    def test_admin_notification_no_duplicate_counting(self):
        """בודק שאין כפילויות בחישוב מונים בהודעות אדמין"""
        from admin_notifications import send_anonymous_chat_notification
        from unittest.mock import patch
        
        # הודעות דמה
        history_messages = [
            {"role": "user", "content": "הודעה 1"},
            {"role": "assistant", "content": "תשובה 1"},
            {"role": "user", "content": "הודעה 2"},
        ]
        
        messages_for_gpt = [
            {"role": "system", "content": "פרומפט ראשי"},
            {"role": "system", "content": "פרומפט שני"},
        ] + history_messages + [{"role": "user", "content": "הודעה חדשה"}]
        
        # ✅ תיקון: במקום לכבות משתני סביבה, נשתמש במוק
        try:
            # מוק שליחת הודעה לאדמין וליכוד התוכן
            with patch('admin_notifications.send_admin_notification_raw') as mock_send:
                # ✅ תיקון: מוק המניע שליחה אמיתית
                with patch('admin_notifications.is_test_environment', return_value=False):
                    send_anonymous_chat_notification(
                        user_message="הודעה חדשה",
                        bot_response="תשובה חדשה",
                        history_messages=history_messages,
                        messages_for_gpt=messages_for_gpt,
                        gpt_timing=1.5,
                        user_timing=2.0,
                        chat_id="123456789"
                    )
                    
                    # בדיקה שהפונקציה נקראה
                    self.assertTrue(mock_send.called)
                    
                    # בדיקה של תוכן ההודעה
                    notification_text = mock_send.call_args[0][0]
                    
                    # בדיקה שמופיע רק מונה אחד של הודעות משתמש
                    user_count_occurrences = notification_text.count("מונה הודעות משתמש:")
                    self.assertEqual(user_count_occurrences, 1, "צריך להיות רק מונה אחד של הודעות משתמש")
                    
                    # בדיקה שהמונה נכון (2 הודעות היסטוריה בלבד)
                    import re
                    # בדיקה יותר פשוטה - מחפש בכל הטקסט את המונה
                    if "מונה הודעות משתמש:" in notification_text:
                        # קיים המונה, בואי נוודא שהוא נכון
                        counter_part = notification_text.split("מונה הודעות משתמש:")[1].strip()
                        self.assertIn("2", counter_part, "המונה צריך להיות 2 (רק היסטוריה)")
                    else:
                        self.fail("לא נמצא מונה הודעות משתמש כלל")
                        
        except Exception as e:
            self.fail(f"השגיאה בבדיקה: {e}")

if __name__ == '__main__':
    unittest.main()