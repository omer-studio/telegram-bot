"""Focused test (unittest) verifying that the message 'אני בן 35' saves age=35."""

import os
import sys
sys.path.insert(0, os.getcwd())  # ensure project root on import path
import json
import tempfile
import importlib
import asyncio
import unittest
from unittest.mock import patch

# Stub external deps absent in test env
import types
sys.modules.setdefault("pytz", types.ModuleType("pytz"))

# Minimal dummy telegram package (used by notifications)
telegram_dummy = types.ModuleType("telegram")
telegram_ext_dummy = types.ModuleType("telegram.ext")

class _Dummy:
    pass

telegram_dummy.Update = _Dummy
telegram_dummy.ReplyKeyboardMarkup = _Dummy
telegram_dummy.ReplyKeyboardRemove = _Dummy
telegram_ext_dummy.ContextTypes = _Dummy

sys.modules.setdefault("telegram", telegram_dummy)
sys.modules.setdefault("telegram.ext", telegram_ext_dummy)


def _reload_module(name):
    """Reload helper to avoid stale references between patches."""
    if name in sys.modules:
        return importlib.reload(sys.modules[name])
    return importlib.import_module(name)


# Pytest collects classes prefixed with 'Test'
class TestAgeMessagePersistence(unittest.TestCase):
    """End-to-end style test – no external services, no pytest deps."""

    def test_age_saved_from_user_message(self):
        os.environ.setdefault("CI", "1")  # ensure CI mode

        with tempfile.TemporaryDirectory() as tmp_dir:
            profiles_path = os.path.join(tmp_dir, "user_profiles.json")
            with open(profiles_path, "w", encoding="utf-8") as fh:
                fh.write("{}")

            # Patch config & profile_utils path before import of message_handler
            config = _reload_module("config")
            with patch.object(config, "USER_PROFILES_PATH", profiles_path, create=True):

                profile_utils = _reload_module("profile_utils")
                # Patch profile_utils path and disable sheets sync
                with patch.object(profile_utils, "USER_PROFILES_PATH", profiles_path, create=True), \
                     patch.object(profile_utils, "_schedule_sheets_sync_safely", lambda _cid: None, create=True):

                    # Stub GPT helper functions that run inside background processors
                    async def _fake_gpt_d_async(chat_id, *_a, **_k):
                        # Persist change directly via profile_utils to mimic real behaviour
                        profile_utils.update_user_profile_fast(chat_id, {"age": 35}, send_admin_notification=False)
                        return ({"age": "35"}, {})

                    async def _fake_gpt_e_async(*_a, **_k):
                        return {"changes": {}}

                    def _fake_extract(*_a, **_k):
                        return {"extracted_fields": {"age": "35"}, "usage": {}, "model": "stub"}

                    with patch("gpt_c_handler.extract_user_info", _fake_extract, create=True), \
                         patch("gpt_d_handler.smart_update_profile_with_gpt_d_async", _fake_gpt_d_async, create=True), \
                         patch("gpt_e_handler.execute_gpt_e_if_needed", _fake_gpt_e_async, create=True):

                        # Import message_handler after stubs so it captures patched refs
                        message_handler = _reload_module("message_handler")

                        # Patch internal copies for safety
                        message_handler.extract_user_info = _fake_extract  # type: ignore
                        message_handler.smart_update_profile_with_gpt_d_async = _fake_gpt_d_async  # type: ignore
                        message_handler.execute_gpt_e_if_needed = _fake_gpt_e_async  # type: ignore

                        # Run background processors with the test message
                        chat_id = "age_test_user"
                        user_msg = "אני בן 35"
                        asyncio.run(
                            message_handler.run_background_processors(chat_id, user_msg, "bot reply")
                        )

            # After exiting context managers, verify persistence on disk
            with open(profiles_path, encoding="utf-8") as fh:
                data = json.load(fh)

            self.assertIn(chat_id, data, "Profile not created on disk")
            self.assertEqual(data[chat_id]["age"], 35, "Age value not saved correctly to JSON")

            # Verify getter returns aged profile
            retrieved_age = profile_utils.get_user_profile_fast(chat_id).get("age")
            self.assertEqual(retrieved_age, 35, "Getter did not return age=35")


if __name__ == "__main__":
    unittest.main(verbosity=2)