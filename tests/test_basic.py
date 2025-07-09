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
        
        # מאחה שליחת הודעה לאדמין וליכוד התוכן
        with patch('admin_notifications.send_admin_notification_raw') as mock_send:
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
            print(f"\nDEBUG: Notification text:\n{repr(notification_text)}\n")
            
            # בדיקה שמופיע רק מונה אחד של הודעות משתמש
            user_count_occurrences = notification_text.count("מונה הודעות משתמש:")
            self.assertEqual(user_count_occurrences, 1, "צריך להיות רק מונה אחד של הודעות משתמש")
            
            # בדיקה שהמונה נכון (2 הודעות היסטוריה + 1 חדשה = 3)
            import re
            counter_match = re.search(r'מונה הודעות משתמש: (\d+) \(היסטוריה: (\d+)\)', notification_text)
            self.assertIsNotNone(counter_match, "לא נמצא מונה הודעות משתמש בפורמט הנכון")
            
            total_messages = int(counter_match.group(1))
            history_messages_count = int(counter_match.group(2))
            
            self.assertEqual(total_messages, 3, "המונה הכולל צריך להיות 3")
            self.assertEqual(history_messages_count, 2, "מונה ההיסטוריה צריך להיות 2")
            
            # בדיקה שהסיסטם פרומפטים בשורה אחת
            system_prompt_lines = [line for line in notification_text.split('\n') if 'סיסטם פרומט' in line]
            self.assertEqual(len(system_prompt_lines), 1, "כל הסיסטם פרומפטים צריכים להיות באותה שורה")

if __name__ == '__main__':
    unittest.main()