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
        
        # 🔧 זמנית לבטל את סביבת הבדיקה כדי שהפונקציה תעבוד
        original_ci = os.environ.get("CI")
        original_testing = os.environ.get("TESTING")
        original_pytest = os.environ.get("PYTEST_CURRENT_TEST")
        
        # הסרת כל משתני הסביבה שמזהים בדיקה
        if "CI" in os.environ:
            del os.environ["CI"]
        if "TESTING" in os.environ:
            del os.environ["TESTING"]
        if "PYTEST_CURRENT_TEST" in os.environ:
            del os.environ["PYTEST_CURRENT_TEST"]
        
        try:
            # מאחה שליחת הודעה לאדמין וליכוד התוכן
            with patch('admin_notifications.send_admin_notification_raw') as mock_send, \
                 patch('db_manager.get_user_message_count') as mock_get_count:
                
                # הגדרת מספר הודעות משתמש אמיתי (מספר גבוה יותר מההיסטוריה)
                mock_get_count.return_value = 25
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
                total_count_occurrences = notification_text.count("סה״כ הודעות משתמש:")
                self.assertEqual(total_count_occurrences, 1, "צריך להיות רק מונה אחד של סה״כ הודעות משתמש")
                
                # בדיקה שהמונה מציג את המספר האמיתי (25) ולא את המוגבל (2)
                self.assertIn("סה״כ הודעות משתמש:** 25", notification_text, "המונה צריך להציג את המספר האמיתי מהמסד נתונים")
                
                # בדיקה שההיסטוריה ל-GPT עדיין מוצגת נכון
                self.assertIn("נשלחה היסטוריה ל-GPT:", notification_text, "צריך להציג היסטוריה ל-GPT")
                self.assertIn("2 משתמש", notification_text, "צריך להציג 2 הודעות משתמש שנשלחו ל-GPT")
                
                # בדיקה שהסיסטם פרומפטים מוצגים כהלכה
                system_prompt_lines = [line for line in notification_text.split('\n') if 'סיסטם פרומט' in line]
                self.assertGreater(len(system_prompt_lines), 0, "צריך להיות לפחות סיסטם פרומט אחד")
                
                # בדיקה שהפרומפטים נמצאים בהודעה (בשורות נפרדות)
                self.assertIn("סיסטם פרומט 1:", notification_text, "צריך להיות סיסטם פרומפט 1")
                self.assertIn("סיסטם פרומט 2:", notification_text, "צריך להיות סיסטם פרומפט 2")
                
        finally:
            # 🔧 החזרת הגדרת סביבת הבדיקה
            if original_ci is not None:
                os.environ["CI"] = original_ci
            if original_testing is not None:
                os.environ["TESTING"] = original_testing
            if original_pytest is not None:
                os.environ["PYTEST_CURRENT_TEST"] = original_pytest

if __name__ == '__main__':
    unittest.main()