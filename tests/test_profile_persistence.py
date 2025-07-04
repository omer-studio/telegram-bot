import os
import json
import importlib

try:
    import pytest  # type: ignore
except ImportError:  # pragma: no cover
    pytest = None  # type: ignore

# Skip entire module in CI to avoid Google Sheets credential issues
if (os.getenv("CI") or os.getenv("GITHUB_ACTIONS")) and pytest is not None:
    pytest.skip("Google Sheets tests skipped in CI", allow_module_level=True)


def _reload_module(mod_name):
    import sys
    if mod_name in sys.modules:
        return importlib.reload(sys.modules[mod_name])
    return importlib.import_module(mod_name)


def test_profile_age_persistence(tmp_path, monkeypatch):
    """Ensure that when we update a user's age it is persisted to disk."""
    # -- Arrange -----------------------------------------------------------------
    # Simulate CI environment so external services are stubbed
    os.environ.setdefault("CI", "1")

    # Reload config to pick up CI env flag (if already imported)
    config = _reload_module("config")

    # Create temporary profile file and patch paths
    profiles_file = tmp_path / "user_profiles.json"
    profiles_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(config, "USER_PROFILES_PATH", str(profiles_file), raising=False)

    # Import/Reload profile_utils after patching config
    profile_utils = _reload_module("profile_utils")
    monkeypatch.setattr(profile_utils, "USER_PROFILES_PATH", str(profiles_file), raising=False)

    # Stub heavy external interactions to keep test isolated
    monkeypatch.setattr(profile_utils, "_schedule_sheets_sync_safely", lambda _cid: None, raising=False)

    import sheets_core  # imported after CI env flag
    monkeypatch.setattr(sheets_core, "generate_summary_from_profile_data", lambda _d: "", raising=False)

    chat_id = "test_chat_id"

    # -- Act ----------------------------------------------------------------------
    success = profile_utils.update_user_profile_fast(chat_id, {"age": 35}, send_admin_notification=False)

    # -- Assert -------------------------------------------------------------------
    assert success is True, "Profile update should return True"

    # The age must be persisted in the JSON file
    with open(profiles_file, encoding="utf-8") as fh:
        data_on_disk = json.load(fh)
    assert data_on_disk[chat_id]["age"] == 35

    # The helper getter should also return the updated age
    assert profile_utils.get_user_profile_fast(chat_id)["age"] == 35


def test_admin_notification_on_profile_update(monkeypatch):
    """Ensure admin notification is triggered by run_background_processors."""

    import asyncio

    # Prepare environment
    os.environ.setdefault("CI", "1")

    # Reload base config & profile utils first
    config = _reload_module("config")
    profile_utils = _reload_module("profile_utils")

    # ------------------------------------------------------------------
    # Stub GPT helpers BEFORE importing message_handler so that the module
    # picks up the patched functions (it imports them at module import time).
    # ------------------------------------------------------------------

    # GPT-C – sync function executed in a thread
    def _fake_extract(*_a, **_k):
        return {"extracted_fields": {"age": "35"}, "usage": {}, "model": "stub"}

    async def _fake_gpt_d_async(*_a, **_k):
        return ({"age": "35"}, {})

    async def _fake_gpt_e_async(*_a, **_k):
        return {"changes": {}}

    monkeypatch.setattr("gpt_c_handler.extract_user_info", _fake_extract, raising=False)
    monkeypatch.setattr("gpt_d_handler.smart_update_profile_with_gpt_d_async", _fake_gpt_d_async, raising=False)
    monkeypatch.setattr("gpt_e_handler.execute_gpt_e_if_needed", _fake_gpt_e_async, raising=False)

    # Now import message_handler – it will use the patched symbols
    message_handler = _reload_module("message_handler")

    # For extra safety, patch the copies inside message_handler as well
    monkeypatch.setattr(message_handler, "extract_user_info", _fake_extract, raising=False)
    monkeypatch.setattr(message_handler, "smart_update_profile_with_gpt_d_async", _fake_gpt_d_async, raising=False)
    monkeypatch.setattr(message_handler, "execute_gpt_e_if_needed", _fake_gpt_e_async, raising=False)

    # Capture admin notifications
    sent_msgs = []
    def _fake_admin_notify(msg):
        sent_msgs.append(msg)
    monkeypatch.setattr("notifications.send_admin_notification_raw", _fake_admin_notify, raising=False)

    # Run the background processor
    chat_id_sample = "chat_flow"
    asyncio.run(message_handler.run_background_processors(chat_id_sample, "אני בן 35", "תודה"))

    assert sent_msgs, "Admin notification should have been sent"
    # Verify content includes chat id and GPT indication
    combined = "\n".join(sent_msgs)
    assert chat_id_sample in combined, "chat_id missing from admin notification"
    assert "GPT" in combined or "GPT-C" in combined, "Notification should mention GPT components"
    assert "שדות" in combined, "Notification should mention number of fields changed"
    assert "GPT-C" in combined or "GPT-D" in combined, "GPT component tag missing"
    assert any(token in combined for token in ["age", "גיל", "35"]), "Updated field details/value missing in notification"


def test_send_admin_notification_raw(monkeypatch):
    """Verify that notifications.send_admin_notification_raw uses requests.post correctly."""
    import notifications
    captured = {}
    class DummyResp:  # simple stand-in for requests.Response
        status_code = 200

    def fake_post(url, data=None, timeout=10):
        captured['url'] = url
        captured['data'] = data
        return DummyResp()

    monkeypatch.setattr("notifications.requests.post", fake_post, raising=False)

    notifications.send_admin_notification_raw("hello test")

    assert captured, "requests.post should have been called"
    assert "chat_id" in captured['data'], "chat_id missing from payload"


def test_send_admin_notification(monkeypatch):
    """Verify that notifications.send_admin_notification posts correctly."""
    import notifications
    sent = {}

    class _Resp:
        status_code = 200

    def fake_post(url, data=None, timeout=10):
        sent['data'] = data
        return _Resp()

    monkeypatch.setattr("notifications.requests.post", fake_post, raising=False)

    notifications.send_admin_notification("hello test msg")

    assert sent, "requests.post not called"
    assert sent['data']["parse_mode"], "parse_mode should exist"


def test_profile_overview_admin_notification(monkeypatch):
    """Ensure _send_admin_profile_overview_notification constructs correct content."""
    import profile_utils as pu
    import notifications

    captured = {}

    def fake_raw(msg):
        captured['msg'] = msg

    monkeypatch.setattr(notifications, "send_admin_notification_raw", fake_raw, raising=False)

    chat_id = "999999"
    gpt_c_changes = [{"field": "age", "old_value": None, "new_value": "30", "change_type": "added"}]

    pu._send_admin_profile_overview_notification(
        chat_id=chat_id,
        user_msg="אני בן 30",
        gpt_c_changes=gpt_c_changes,
        gpt_d_changes=[],
        gpt_e_changes=[],
        gpt_c_info="GPT-C info",
        gpt_d_info="GPT-D info",
        gpt_e_info="GPT-E info",
        summary="גיל: 30"
    )

    assert captured, "Admin overview notification not sent"
    text = captured['msg']
    assert chat_id in text, "chat_id missing in overview notification"
    assert "age" in text or "גיל" in text, "Updated field name missing"
    assert "GPT-C" in text, "GPT-C section missing"


def test_admin_notification_content_on_profile_update(monkeypatch):
    """Minimal focused test – run_background_processors triggers notification with correct content."""

    import asyncio
    import message_handler as mh
    import notifications

    chat_id = "notif_test"
    user_msg = "אני גר בתל אביב"

    # Capture admin notification
    captured = {}

    def fake_notify(msg):
        captured['msg'] = msg

    monkeypatch.setattr(notifications, "send_admin_notification_raw", fake_notify, raising=False)

    # Stub GPT handlers to avoid heavy calls
    def _fake_extract_loc(*_a, **_k):
        return {"extracted_fields": {"location": "תל אביב"}, "usage": {}, "model": "stub"}

    async def _fake_gpt_d_async_loc(*_a, **_k):
        return ({"location": "תל אביב"}, {})

    async def _fake_gpt_e_async_loc(*_a, **_k):
        return {"changes": {}}

    monkeypatch.setattr("gpt_c_handler.extract_user_info", _fake_extract_loc, raising=False)
    monkeypatch.setattr("gpt_d_handler.smart_update_profile_with_gpt_d_async", _fake_gpt_d_async_loc, raising=False)
    monkeypatch.setattr("gpt_e_handler.execute_gpt_e_if_needed", _fake_gpt_e_async_loc, raising=False)

    # Patch copies inside message_handler as well (already imported as mh)
    monkeypatch.setattr(mh, "extract_user_info", _fake_extract_loc, raising=False)
    monkeypatch.setattr(mh, "smart_update_profile_with_gpt_d_async", _fake_gpt_d_async_loc, raising=False)
    monkeypatch.setattr(mh, "execute_gpt_e_if_needed", _fake_gpt_e_async_loc, raising=False)

    # Run background processors
    asyncio.run(mh.run_background_processors(chat_id, user_msg, "דיון"))

    assert captured, "Notification not sent"
    msg = captured['msg']
    assert chat_id in msg, "chat_id missing"
    assert any(token in msg for token in ["location", "מיקום", "תל אביב"]), "Updated location details/value missing"
    assert "GPT-C" in msg, "GPT component missing"


# ---------------------------------------------------------------
# New test – verifies age field update path with Hebrew text
# ---------------------------------------------------------------


def test_admin_notification_age_update(monkeypatch):
    """Ensure notification includes chat_id, 'age' field and GPT-C when age is updated."""

    import asyncio
    import message_handler as mh
    import notifications

    chat_id = "chat35"
    user_msg = "אני בן 35"

    captured = {}

    def fake_notify(msg):
        captured['msg'] = msg

    monkeypatch.setattr(notifications, "send_admin_notification_raw", fake_notify, raising=False)

    # Stub GPT handlers to avoid heavy calls
    async def _fake_gpt_d_async_age(*_a, **_k):
        return ({"age": "35"}, {})

    async def _fake_gpt_e_async_age(*_a, **_k):
        return {"changes": {}}

    def _fake_extract_age(*_a, **_k):
        return {"extracted_fields": {"age": "35"}, "usage": {}, "model": "stub"}

    monkeypatch.setattr("gpt_c_handler.extract_user_info", _fake_extract_age, raising=False)
    monkeypatch.setattr("gpt_d_handler.smart_update_profile_with_gpt_d_async", _fake_gpt_d_async_age, raising=False)
    monkeypatch.setattr("gpt_e_handler.execute_gpt_e_if_needed", _fake_gpt_e_async_age, raising=False)

    # Patch copies inside message_handler (already imported as mh)
    monkeypatch.setattr(mh, "extract_user_info", _fake_extract_age, raising=False)
    monkeypatch.setattr(mh, "smart_update_profile_with_gpt_d_async", _fake_gpt_d_async_age, raising=False)
    monkeypatch.setattr(mh, "execute_gpt_e_if_needed", _fake_gpt_e_async_age, raising=False)

    asyncio.run(mh.run_background_processors(chat_id, user_msg, "תשובה"))

    assert captured, "Notification not sent"
    txt = captured['msg']
    assert chat_id in txt, "chat_id missing in notification"
    assert any(token in txt for token in ["age", "גיל", "35"]), "Age update details/value missing in notification"
    assert "GPT-C" in txt, "GPT component GPT-C missing in notification"