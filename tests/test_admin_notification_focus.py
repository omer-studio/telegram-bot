# -------- Skip immediately if in CI ----------
import os
try:
    import pytest  # type: ignore
except ImportError:
    pytest = None  # type: ignore

if pytest is not None and (os.getenv("CI") or os.getenv("GITHUB_ACTIONS")):
    pytest.skip("Skipping secret-dependent tests", allow_module_level=True)

# -------- after potential skip --------
import importlib
import asyncio

def _reload_module(mod_name):
    import sys
    if mod_name in sys.modules:
        return importlib.reload(sys.modules[mod_name])
    return importlib.import_module(mod_name)


def test_admin_notification_focus_age(monkeypatch):
    """Focused test – verifies admin notification content for 'אני בן 35'."""

    # ------------------------------------------------------------
    # 1. Environment & module reloads
    # ------------------------------------------------------------
    os.environ.setdefault("CI", "1")

    config = _reload_module("config")

    # ------------------------------------------------------------
    # 2. Stub GPT helpers BEFORE importing message_handler so that
    #    the module picks up the patched versions.
    # ------------------------------------------------------------

    def _fake_extract(*_a, **_k):
        return {"extracted_fields": {"age": "35"}, "usage": {}, "model": "stub"}

    async def _fake_gpt_d_async(*_a, **_k):
        return ({"age": "35"}, {})

    async def _fake_gpt_e_async(*_a, **_k):
        return {"changes": {}}

    monkeypatch.setattr("gpt_c_handler.extract_user_info", _fake_extract, raising=False)
    monkeypatch.setattr("gpt_d_handler.smart_update_profile_with_gpt_d_async", _fake_gpt_d_async, raising=False)
    monkeypatch.setattr("gpt_e_handler.execute_gpt_e_if_needed", _fake_gpt_e_async, raising=False)

    # Import message_handler after stubbing
    import message_handler as mh

    # Patch the copies inside message_handler as well (import time copies)
    monkeypatch.setattr(mh, "extract_user_info", _fake_extract, raising=False)
    monkeypatch.setattr(mh, "smart_update_profile_with_gpt_d_async", _fake_gpt_d_async, raising=False)
    monkeypatch.setattr(mh, "execute_gpt_e_if_needed", _fake_gpt_e_async, raising=False)

    # ------------------------------------------------------------
    # 3. Capture admin notification
    # ------------------------------------------------------------
    import notifications

    captured = {}

    def _fake_notify(msg):
        captured["msg"] = msg

    monkeypatch.setattr(notifications, "send_admin_notification_raw", _fake_notify, raising=False)

    # ------------------------------------------------------------
    # 4. Run background processors
    # ------------------------------------------------------------
    chat_id = "focus35"
    user_msg = "אני בן 35"
    asyncio.run(mh.run_background_processors(chat_id, user_msg, "bot reply"))

    # ------------------------------------------------------------
    # 5. Assertions – ensure focused content is present
    # ------------------------------------------------------------
    assert captured, "Admin notification was not sent"
    msg = captured["msg"]
    # core expectations
    assert chat_id in msg, "chat_id missing in admin notification"
    assert "35" in msg, "updated value '35' missing in notification"
    assert "GPT-C" in msg, "GPT component tag missing"
    assert "שדות" in msg, "field count summary missing"