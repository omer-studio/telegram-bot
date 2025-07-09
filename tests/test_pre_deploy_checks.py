# --- Skip immediately in CI ---
import os
try:
    import pytest  # type: ignore
except ImportError:
    pytest = None  # type: ignore

if pytest is not None and (os.getenv("CI") or os.getenv("GITHUB_ACTIONS")):
    pytest.skip("Skipping secret-dependent tests", allow_module_level=True)

# Only after potential skip
import importlib


def _reload_module(mod_name):
    import sys
    if mod_name in sys.modules:
        return importlib.reload(sys.modules[mod_name])
    return importlib.import_module(mod_name)


def test_pre_deploy_basic(monkeypatch):
    """Run lightweight versions of critical pre-deploy checks."""
    os.environ.setdefault("CI", "1")

    # שינוי תיקיית עבודה לשורש הפרויקט
    original_cwd = os.getcwd()
    
    # אם אנחנו בתיקיית tests, נעבור לתיקיית ההורה
    if os.path.basename(original_cwd) == 'tests':
        os.chdir('..')
    
    try:
        # Reload to pick up CI flag
        pd = _reload_module("comprehensive_deploy_check")

        # Stub the heavy GPT-A real call
        monkeypatch.setattr(pd.ComprehensiveDeployChecker, "check_gpt_a_functionality", lambda self: (True, []), raising=False)

        # Create checker instance
        checker = pd.ComprehensiveDeployChecker()

        # Run selected critical checks
        ok_syntax, errs_syntax = checker.check_syntax_and_imports()
        ok_config, errs_config = checker.check_critical_configuration()

        assert ok_syntax, f"Syntax/import check failed: {errs_syntax}"
        assert ok_config, f"Config check failed: {errs_config}"
    
    finally:
        # החזרת תיקיית העבודה המקורית
        os.chdir(original_cwd)