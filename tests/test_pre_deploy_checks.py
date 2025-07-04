import os
import importlib

try:
    import pytest  # type: ignore
except ImportError:
    pytest = None  # type: ignore

if (os.getenv("CI") or os.getenv("GITHUB_ACTIONS")) and pytest is not None:
    pytest.skip("Skipping tests requiring external credentials in CI", allow_module_level=True)


def _reload_module(mod_name):
    import sys
    if mod_name in sys.modules:
        return importlib.reload(sys.modules[mod_name])
    return importlib.import_module(mod_name)


def test_pre_deploy_basic(monkeypatch):
    """Run lightweight versions of critical pre-deploy checks."""
    os.environ.setdefault("CI", "1")

    # Reload to pick up CI flag
    pd = _reload_module("pre_deploy_critical_check")

    # Stub the heavy GPT-A real call
    monkeypatch.setattr(pd, "check_gpt_a_basic_functionality", lambda: (True, []), raising=False)

    # Run selected critical checks
    ok_syntax, errs_syntax = pd.check_syntax_and_imports()
    ok_config, errs_config = pd.check_critical_configuration()

    assert ok_syntax, f"Syntax/import check failed: {errs_syntax}"
    assert ok_config, f"Config check failed: {errs_config}"