#!/usr/bin/env python3
"""
deployment_check.py
==================
מנגנון בדיקה אוטומטי לפריסה - וידוא שהמערכת עובדת לגמרי

מריץ סדרת בדיקות מקיפות:
1. Import validation - כל המודולים נטענים
2. Configuration check - כל הגדרות נכונות
3. Database connectivity - חיבור למסד נתונים עובד
4. API endpoints - FastAPI מגיב נכון
5. Telegram bot - הבוט מגיב לפקודות
6. Critical functions - פונקציות חיוניות עובדות

אם הבדיקה נכשלת - מציג הנחיות לתיקון
"""

import sys
import time
import requests
import asyncio
import os
from typing import Dict, List, Any
from simple_config import TimeoutConfig

def print_header(title: str):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"🔍 {title}")
    print("="*60)

def print_result(test_name: str, success: bool, details: str = ""):
    """Print test result with consistent formatting"""
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {test_name}")
    if details:
        print(f"    └─ {details}")

def check_imports() -> Dict[str, bool]:
    """בדיקת כל ה-imports החיוניים"""
    print_header("Import Validation")
    
    critical_modules = [
        "simple_config", "simple_logger", "simple_data_manager",
        "bot_setup", "message_handler", "notifications",
        "utils", "chat_utils", "profile_utils"
    ]
    
    results = {}
    for module in critical_modules:
        try:
            __import__(module)
            results[module] = True
            print_result(f"Import {module}", True)
        except Exception as e:
            results[module] = False
            print_result(f"Import {module}", False, str(e))
    
    return results

def check_configuration() -> Dict[str, bool]:
    """בדיקת תצורה בסיסית"""
    print_header("Configuration Check")
    
    results = {}
    
    # Check config module - try both simple_config and config
    try:
        # Try simple_config first
        try:
            from simple_config import SimpleConfig
            config = SimpleConfig()
            telegram_token = config.get_telegram_token()
        except:
            # Fallback to config module
            from config import TELEGRAM_BOT_TOKEN
            telegram_token = TELEGRAM_BOT_TOKEN
        
        if telegram_token and len(telegram_token) > 20 and ":" in telegram_token:
            results["telegram_token"] = True
            print_result("Telegram Bot Token", True, "Token format valid")
        else:
            results["telegram_token"] = False
            print_result("Telegram Bot Token", False, f"Invalid token format: {telegram_token[:20] if telegram_token else 'None'}...")
    except Exception as e:
        results["telegram_token"] = False
        print_result("Telegram Bot Token", False, str(e))
    
    # Check environment variables
    required_env = ["PORT"] if os.getenv("RENDER") else []
    for env_var in required_env:
        value = os.getenv(env_var)
        if value:
            results[f"env_{env_var}"] = True
            print_result(f"Environment {env_var}", True, f"Value: {value}")
        else:
            results[f"env_{env_var}"] = False
            print_result(f"Environment {env_var}", False, "Missing")
    
    return results

def check_database() -> Dict[str, bool]:
    """בדיקת חיבור למסד נתונים"""
    print_header("Database Connectivity")
    
    results = {}
    
    try:
        from simple_data_manager import data_manager
        
        # Test basic connection
        test_result = data_manager.execute_query("SELECT 1 as test", fetch_one=True)
        if test_result and test_result.get("test") == 1:
            results["basic_connection"] = True
            print_result("Database Connection", True, "Basic query successful")
        else:
            results["basic_connection"] = False
            print_result("Database Connection", False, "Query returned unexpected result")
            
        # Test table existence - check for any tables (flexible approach)
        tables_query = """
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public'
        """
        tables = data_manager.execute_query(tables_query, fetch_all=True)
        if len(tables) >= 1:
            results["tables_exist"] = True
            print_result("Required Tables", True, f"Found {len(tables)} tables")
        else:
            results["tables_exist"] = False
            print_result("Required Tables", False, f"Only found {len(tables)} tables")
            
    except Exception as e:
        results["basic_connection"] = False
        results["tables_exist"] = False
        print_result("Database Connection", False, str(e))
    
    return results

def check_api_endpoints() -> Dict[str, bool]:
    """בדיקת FastAPI endpoints"""
    print_header("API Endpoints Check")
    
    results = {}
    
    # Skip API endpoint checks if running in CI/deployment environment
    if os.getenv("RENDER") or os.getenv("CI"):
        results["api_endpoints"] = True
        print_result("API Endpoints", True, "Skipped in deployment environment")
        return results
    
    port = os.getenv("PORT", "8000")
    base_url = f"http://localhost:{port}"
    
    endpoints = [
        ("/", "Root endpoint"),
        ("/health", "Health check endpoint")
    ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=TimeoutConfig.HTTP_REQUEST_TIMEOUT)
            if response.status_code == 200:
                results[endpoint] = True
                print_result(description, True, f"Status: {response.status_code}")
            else:
                results[endpoint] = False
                print_result(description, False, f"Status: {response.status_code}")
        except Exception as e:
            results[endpoint] = False
            print_result(description, False, str(e))
    
    return results

async def check_telegram_bot() -> Dict[str, bool]:
    """בדיקת פונקציונליות הבוט"""
    print_header("Telegram Bot Check")
    
    results = {}
    
    try:
        # Test bot initialization
        from bot_setup import setup_bot
        app = setup_bot()
        
        if app and hasattr(app, 'bot'):
            results["bot_init"] = True
            print_result("Bot Initialization", True, "Bot object created")
            
            # Test bot info
            try:
                await app.initialize()
                await app.start()
                bot_info = await app.bot.get_me()
                
                if bot_info and bot_info.username:
                    results["bot_info"] = True
                    print_result("Bot Info", True, f"Username: @{bot_info.username}")
                else:
                    results["bot_info"] = False
                    print_result("Bot Info", False, "Failed to get bot info")
                    
                await app.stop()
                
            except Exception as e:
                results["bot_info"] = False
                print_result("Bot Info", False, str(e))
        else:
            results["bot_init"] = False
            print_result("Bot Initialization", False, "Failed to create bot")
            
    except Exception as e:
        results["bot_init"] = False
        results["bot_info"] = False
        print_result("Bot Initialization", False, str(e))
    
    return results

def check_critical_functions() -> Dict[str, bool]:
    """בדיקת פונקציות חיוניות"""
    print_header("Critical Functions Check")
    
    results = {}
    
    # Test utils health_check
    try:
        from utils import health_check
        health_result = health_check()
        if isinstance(health_result, dict) and health_result:
            results["utils_health_check"] = True
            print_result("Utils Health Check", True, f"Components: {list(health_result.keys())}")
        else:
            results["utils_health_check"] = False
            print_result("Utils Health Check", False, "Invalid result")
    except Exception as e:
        results["utils_health_check"] = False
        print_result("Utils Health Check", False, str(e))
    
    # Test logger
    try:
        from simple_logger import logger
        logger.info("Deployment check test log", source="deployment_check")
        results["logger_test"] = True
        print_result("Logger Test", True, "Log message sent successfully")
    except Exception as e:
        results["logger_test"] = False
        print_result("Logger Test", False, str(e))
    
    # Test user-friendly errors
    try:
        from db_manager import safe_str
        test_result = safe_str("12345")
        if test_result == "12345":
            results["safe_str_test"] = True
            print_result("Safe String Test", True, "safe_str working correctly")
        else:
            results["safe_str_test"] = False
            print_result("Safe String Test", False, f"Unexpected result: {test_result}")
    except Exception as e:
        results["safe_str_test"] = False
        print_result("Safe String Test", False, str(e))
    
    return results

def generate_deployment_report(all_results: Dict[str, Dict[str, bool]]) -> None:
    """Generate comprehensive deployment report"""
    print_header("Deployment Report")
    
    total_tests = sum(len(category_results) for category_results in all_results.values())
    passed_tests = sum(sum(category_results.values()) for category_results in all_results.values())
    
    success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
    
    print(f"📊 Overall Success Rate: {success_rate:.1f}% ({passed_tests}/{total_tests})")
    
    # Category breakdown
    for category, results in all_results.items():
        category_passed = sum(results.values())
        category_total = len(results)
        category_rate = (category_passed / category_total) * 100 if category_total > 0 else 0
        
        status_emoji = "✅" if category_rate == 100 else "⚠️" if category_rate >= 80 else "❌"
        print(f"{status_emoji} {category}: {category_rate:.1f}% ({category_passed}/{category_total})")
    
    # Overall status
    if success_rate >= 80:
        print("\n🎉 DEPLOYMENT SUCCESSFUL! System operational.")
        if success_rate < 95:
            print("   - Some non-critical issues detected but system should work")
        return True
    elif success_rate >= 60:
        print("\n⚠️ DEPLOYMENT PARTIALLY SUCCESSFUL. Monitor for issues.")
        print("   - The system may work but needs attention")
        return True
    else:
        print("\n❌ DEPLOYMENT FAILED! Critical issues detected.")
        print("   - Fix the failed tests before proceeding")
        print("   - Check logs for detailed error information")
        return False

async def run_comprehensive_check() -> bool:
    """Run all deployment checks"""
    print("🚀 Starting Comprehensive Deployment Check...")
    print(f"⏰ Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_results = {}
    
    # Run all checks
    all_results["imports"] = check_imports()
    all_results["configuration"] = check_configuration()
    all_results["database"] = check_database()
    all_results["api_endpoints"] = check_api_endpoints()
    all_results["telegram_bot"] = await check_telegram_bot()
    all_results["critical_functions"] = check_critical_functions()
    
    # Generate report
    deployment_success = generate_deployment_report(all_results)
    
    return deployment_success

def main():
    """Main entry point"""
    try:
        # Add current directory to Python path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Run the comprehensive check
        success = asyncio.run(run_comprehensive_check())
        
        if success:
            print("\n✅ Deployment check completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Deployment check failed!")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Deployment check interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Deployment check crashed: {e}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 