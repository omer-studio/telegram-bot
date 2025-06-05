import pytest
from unittest.mock import patch, mock_open, MagicMock
from utils import log_error_stat, send_error_stats_report, send_usage_report

def test_log_error_stat_creates_and_updates_file():
    m = mock_open(read_data='{}')
    with patch('os.path.exists', side_effect=lambda p: p.endswith('errors_stats.json') and False), \
         patch('os.makedirs') as makedirs, \
         patch('builtins.open', m):
        log_error_stat('test_error')
        makedirs.assert_called()
        handle = m()
        handle.write.assert_called()

    # בדיקה לעדכון קיים
    m = mock_open(read_data='{"test_error": 1}')
    with patch('os.path.exists', side_effect=lambda p: True), \
         patch('builtins.open', m):
        log_error_stat('test_error')
        handle = m()
        handle.write.assert_called()

def test_send_error_stats_report_no_file():
    with patch('os.path.exists', return_value=False), \
         patch('notifications.send_admin_notification') as send_admin:
        send_error_stats_report()
        send_admin.assert_called_with("אין נתוני שגיאות זמינים.")

def test_send_usage_report_no_log():
    with patch('os.path.exists', return_value=False), \
         patch('notifications.send_admin_notification') as send_admin:
        send_usage_report(1)
        send_admin.assert_called_with("אין לוג usage זמין.") 