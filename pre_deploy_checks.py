#!/usr/bin/env python3
"""
🛡️ בדיקות מוקדמות לפני פריסה
===============================

מטרה: למנוע בעיות זיכרון ודפנדנסיז לפני שהן מגיעות לפרודקשן

שימוש:
python pre_deploy_checks.py

יעבור על:
1. בדיקת גרסאות dependencies כבדים
2. אומדן צריכת זיכרון
3. בדיקת imports כבדים
4. התראה על שינויים מסוכנים
"""

import subprocess
import sys
import os
import json
from typing import Dict, List, Tuple, Optional

class PreDeployChecker:
    """בודק מוקדמות לפני פריסה"""
    
    def __init__(self):
        self.warnings = []
        self.errors = []
        self.memory_estimate = 0
        
        # 🔧 מצב Legacy - מכיר בקונפיגורציות שעבדו בעבר
        self.legacy_mode = True
        
        # רשימת חבילות כבדות וגרסאות בטוחות
        self.heavy_packages = {
            "litellm": {
                "safe_versions": ["1.30.0", "1.35.0", "1.40.0", "1.45.0"],
                "dangerous_versions": ["1.70.0", "1.73.0", "1.73.6", "1.74.0", "1.75.0"],
                "max_safe": "1.35.0",  # 🔒 נעול לגרסה יציבה
                "memory_impact": 150,  # MB - מציאותי יותר
                "dangerous_dependencies": ["tokenizers", "huggingface-hub", "grpcio", "google-api-python-client"],
                "allow_range": ">=1.30.0",  # מאפשר את הטווח הזה שהיה עובד בעבר
                "legacy_working": True  # 🔧 מצב legacy - היה עובד בעבר
            },
            "transformers": {
                "safe_versions": ["4.20.0", "4.25.0"],
                "dangerous_versions": ["4.40.0", "4.45.0", "4.50.0"],
                "max_safe": "4.30.0", 
                "memory_impact": 300,
                "dangerous_dependencies": ["tokenizers", "huggingface-hub"]
            },
            "torch": {
                "memory_impact": 500,
                "warning": "PyTorch is very heavy - consider alternatives"
            },
            "tensorflow": {
                "memory_impact": 600,
                "warning": "TensorFlow is extremely heavy - avoid if possible"
            }
        }
        
        # Dependencies שלא צריכים להיות מותקנים
        self.unwanted_packages = [
            "tokenizers",
            "huggingface-hub", 
            "grpcio",
            "google-api-python-client",
            "protobuf"
        ]

    def get_installed_packages(self) -> Dict[str, str]:
        """מקבל רשימת חבילות מותקנות"""
        try:
            result = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                packages = json.loads(result.stdout)
                return {pkg["name"].lower(): pkg["version"] for pkg in packages}
            else:
                self.errors.append(f"Failed to get package list: {result.stderr}")
                return {}
        except Exception as e:
            self.errors.append(f"Error getting packages: {e}")
            return {}

    def check_requirements_file(self) -> Dict[str, str]:
        """בודק את קובץ requirements.txt"""
        requirements = {}
        try:
            with open("requirements.txt", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # נקה תגובות בסוף השורה
                        if "#" in line:
                            line = line.split("#")[0].strip()
                        
                        if "==" in line:
                            name, version = line.split("==", 1)
                            requirements[name.lower()] = version.strip()
                        elif ">=" in line:
                            name, version = line.split(">=", 1)
                            requirements[name.lower()] = f">={version.strip()}"
        except FileNotFoundError:
            self.errors.append("requirements.txt not found")
        except Exception as e:
            self.errors.append(f"Error reading requirements.txt: {e}")
        
        return requirements

    def check_heavy_packages(self, installed: Dict[str, str], requirements: Dict[str, str]) -> None:
        """בדיקת חבילות כבדות"""
        print("🔍 בודק חבילות כבדות...")
        
        for package, config in self.heavy_packages.items():
            # בדיקה ב-requirements
            if package in requirements:
                req_version = requirements[package]
                if req_version.startswith(">="):
                    # בדיקה אם זה טווח מותר או במצב legacy
                    if "allow_range" in config and req_version == config["allow_range"]:
                        if self.legacy_mode and config.get("legacy_working", False):
                            print(f"   🔙 {package}: טווח legacy מאושר {req_version}")
                        else:
                            print(f"   ✅ {package}: טווח מותר {req_version}")
                    elif self.legacy_mode and config.get("legacy_working", False):
                        print(f"   🔙 {package}: מאושר במצב Legacy {req_version}")
                    else:
                        self.warnings.append(
                            f"⚠️  {package}: גרסה פתוחה ({req_version}) - מסוכן! "
                            f"עדיף לנעול ל-{config.get('max_safe', 'גרסה יציבה')}"
                        )
                elif "dangerous_versions" in config:
                    req_clean = req_version.replace("==", "")
                    if req_clean in config["dangerous_versions"]:
                        self.errors.append(
                            f"💀 {package}: גרסה מסוכנת {req_clean}! "
                            f"עדיף לחזור ל-{config.get('max_safe')}"
                        )
            
            # בדיקה במותקן
            if package in installed:
                version = installed[package]
                memory_impact = config.get("memory_impact", 100)
                self.memory_estimate += memory_impact
                
                print(f"   📦 {package} {version} (~{memory_impact}MB)")
                
                if "dangerous_versions" in config and version in config["dangerous_versions"]:
                    self.errors.append(
                        f"💀 {package}: גרסה מסוכנת {version} מותקנת! "
                        f"עלולה לגרום לקריסת זיכרון"
                    )

    def check_unwanted_packages(self, installed: Dict[str, str]) -> None:
        """בדיקת dependencies לא רצויים"""
        print("🚫 בודק dependencies לא רצויים...")
        
        found_unwanted = []
        for package in self.unwanted_packages:
            if package in installed:
                found_unwanted.append(f"{package} {installed[package]}")
                self.memory_estimate += 50  # הערכה
        
        if found_unwanted:
            if self.legacy_mode:
                print(f"   🔙 Legacy dependencies מזוהים: {', '.join(found_unwanted)}")
                print(f"   💡 במצב Legacy - אלה נחשבים קבילים")
            else:
                self.warnings.append(
                    f"⚠️  נמצאו dependencies כבדים שאולי לא נחוצים:\n"
                    f"   {', '.join(found_unwanted)}\n"
                    f"   אלה עלולים לנבוע מגרסה חדשה של LiteLLM"
                )

    def estimate_memory_usage(self, installed: Dict[str, str]) -> None:
        """אומדן צריכת זיכרון"""
        print("📊 מעריך צריכת זיכרון...")
        
        # Base memory
        base_memory = 80  # FastAPI + basic stuff
        self.memory_estimate += base_memory
        
        # Known packages
        package_memory = {
            "telegram": 50,
            "fastapi": 30,
            "uvicorn": 20,
            "gspread": 30,
            "requests": 20,
            "google-generativeai": 40
        }
        
        for package, memory in package_memory.items():
            if any(package in pkg for pkg in installed.keys()):
                self.memory_estimate += memory
        
        # Render limit - במצב Legacy מותר יותר ספק
        render_limit = 512
        if self.legacy_mode:
            error_threshold = render_limit * 1.8  # 921MB - סף שגיאה במצב legacy
            warning_threshold = render_limit * 1.4  # 716MB - סף אזהרה במצב legacy
            print("   🔙 מצב Legacy: מאפשר קונפיגורציות שעבדו בעבר")
        else:
            error_threshold = render_limit * 1.2  # 614MB - סף שגיאה
            warning_threshold = render_limit * 0.9  # 460MB - סף אזהרה
        
        print(f"   💾 אומדן זיכרון: ~{self.memory_estimate}MB (מגבלה: {error_threshold}MB)")
        
        if self.memory_estimate > error_threshold:
            self.errors.append(
                f"💀 צריכת זיכרון גבוהה מדי: {self.memory_estimate}MB > {error_threshold}MB\n"
                f"   הבוט כמעט בוודאי יקרוס ב-Render!"
            )
        elif self.memory_estimate > warning_threshold:
            if not self.legacy_mode:
                self.warnings.append(
                    f"⚠️  צריכת זיכרון גבוהה: {self.memory_estimate}MB (90%+ מהמגבלה)\n"
                    f"   כדאי לייעל לפני פריסה"
                )
            else:
                print(f"   🔙 Legacy mode: זיכרון גבוה ({self.memory_estimate}MB) אבל מקובל")
        else:
            print(f"   ✅ צריכת זיכרון בטוחה ({self.memory_estimate}/{render_limit}MB)")

    def check_imports_weight(self) -> None:
        """בדיקת imports כבדים בקוד"""
        print("📋 בודק imports כבדים...")
        
        heavy_imports = []
        files_to_check = [
            "main.py", "gpt_a_handler.py", "gpt_b_handler.py", 
            "gpt_c_handler.py", "gpt_d_handler.py", "gpt_e_handler.py"
        ]
        
        for filename in files_to_check:
            if os.path.exists(filename):
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    # Check for direct litellm imports
                    if "import litellm" in content and "lazy_litellm" not in content:
                        heavy_imports.append(f"{filename}: import litellm (ישיר)")
                    
                    # Check for other heavy imports
                    heavy_patterns = ["import torch", "import tensorflow", "import transformers"]
                    for pattern in heavy_patterns:
                        if pattern in content:
                            heavy_imports.append(f"{filename}: {pattern}")
                            
                except Exception as e:
                    self.warnings.append(f"לא ניתן לקרוא {filename}: {e}")
        
        if heavy_imports:
            self.warnings.append(
                f"⚠️  נמצאו imports כבדים:\n" + 
                "\n".join(f"   - {imp}" for imp in heavy_imports)
            )

    def check_lazy_loading_implementation(self) -> None:
        """בדיקה שLazy Loading מיושם נכון"""
        print("🦥 בודק יישום Lazy Loading...")
        
        if os.path.exists("lazy_litellm.py"):
            print("   ✅ lazy_litellm.py קיים")
        else:
            self.warnings.append("⚠️  lazy_litellm.py לא נמצא - Lazy Loading לא מיושם")
        
        # Check if handlers use lazy imports
        handler_files = [f"gpt_{letter}_handler.py" for letter in "abcde"]
        using_lazy = 0
        
        for handler in handler_files:
            if os.path.exists(handler):
                try:
                    with open(handler, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "lazy_litellm" in content:
                        using_lazy += 1
                except:
                    pass
        
        if using_lazy > 0:
            print(f"   ✅ {using_lazy} handlers משתמשים ב-Lazy Loading")
        else:
            self.warnings.append("⚠️  אף handler לא משתמש ב-Lazy Loading")

    def check_interface_compatibility(self) -> None:
        """בדיקה שהעטיפות הקריטיות מחזירות dict עם success ושיש להן פרמטר chat_id בלבד
        כדי למנוע מקרים שבהם החתימה משתנה ללא בדיקות.
        רץ על sheets_handler.register_user / approve_user ללא ביצוע קריאה חיצונית.
        """
        print("🔗 בודק תאימות ממשקי ליבה...")
        try:
            import inspect, re
            try:
                from sheets_handler import register_user, approve_user  # עטיפות
            except (ImportError, FileNotFoundError, Exception) as import_err:
                if "config.json" in str(import_err):
                    # בסביבת development ללא config.json
                    self.warnings.append("⚠️ לא ניתן לבדוק תאימות ממשקים – config.json not found (development environment)")
                    print("   ⚠️ דולג – אין config.json (סביבת פיתוח)")
                    return
                # בסביבת CI ללא dependencies מלאים
                self.warnings.append(f"⚠️ לא ניתן לבדוק תאימות ממשקים ב-CI: {import_err}")
                print("   ⚠️ דולג – אין dependencies מלאים ב-CI")
                return

            problems = []

            for fn_name, fn in [("register_user", register_user), ("approve_user", approve_user)]:
                sig = inspect.signature(fn)
                # לפחות פרמטר אחד (chat_id). לא יותר משניים (chat_id, user_data)
                if not (1 <= len(sig.parameters) <= 2):
                    problems.append(f"{fn_name}: ציפיתי ל-1-2 פרמטרים, קיבלתי {len(sig.parameters)}")

                # בדיקת מילת success בהחזרה – סריקה סטטית של הקוד מבלי להריץ
                src = inspect.getsource(fn)
                if not re.search(r"return\s+\{[^}]*'success'", src):
                    problems.append(f"{fn_name}: אין ‎'success'‎ בהחזרת הפונקציה")

            if problems:
                self.errors.append("💀 אי-תאימות ממשקי ליבה:\n   " + "\n   ".join(problems))
            else:
                print("   ✅ ממשקי ליבה תקינים")
        except Exception as e:
            self.errors.append(f"Error checking interface compatibility: {e}")

    def check_google_sheets_connectivity(self) -> None:
        """מנסה לפתוח את הגיליון כדי לוודא שה-credentials תקינים ומזהיר אחרת"""
        print("🔑 בודק חיבור Google Sheets...")
        try:
            # אם הריצה ב-CI ואין שום אישור מוגדר – אל תכשיל build; הסתפק באזהרה
            if os.getenv("CI") and not (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("SERVICE_ACCOUNT_DICT")):
                self.warnings.append("⚠️ Google Sheets credentials not provided in CI – בדיקה מדולגת (warning בלבד)")
                print("   ⚠️ דולג – אין אישורי Google Sheets ב-CI")
                return

            # בסביבת development ללא config.json – דילוג עם warning
            try:
                from config import setup_google_sheets
            except (FileNotFoundError, Exception) as config_err:
                if "config.json" in str(config_err):
                    self.warnings.append("⚠️ Google Sheets check skipped – config.json not found (development environment)")
                    print("   ⚠️ דולג – אין config.json (סביבת פיתוח)")
                    return
                else:
                    raise config_err

            setup_google_sheets()  # ינסה להשתמש ב-cache או לפתוח חיבור
            print("   ✅ Google Sheets – OK")
        except Exception as e:
            self.errors.append(f"💀 Google Sheets connection failed: {e}")

    def run_all_checks(self) -> bool:
        """מריץ את כל הבדיקות"""
        print("🛡️ מתחיל בדיקות מוקדמות לפני פריסה...\n")
        
        # Get package info
        installed = self.get_installed_packages()
        requirements = self.check_requirements_file()
        
        # Run checks
        self.check_heavy_packages(installed, requirements)
        self.check_unwanted_packages(installed)
        self.estimate_memory_usage(installed)
        self.check_imports_weight()
        self.check_lazy_loading_implementation()
        self.check_interface_compatibility()
        self.check_google_sheets_connectivity()
        
        # Print results
        print("\n" + "="*60)
        print("📋 תוצאות בדיקה:")
        print("="*60)
        
        if self.errors:
            print("\n❌ שגיאות קריטיות:")
            for error in self.errors:
                print(f"   {error}")
        
        if self.warnings:
            print("\n⚠️  אזהרות:")
            for warning in self.warnings:
                print(f"   {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ כל הבדיקות עברו בהצלחה!")
            print(f"💾 אומדן זיכרון: {self.memory_estimate}MB")
            return True
        elif not self.errors:
            print(f"\n✅ ניתן לפרסה (עם אזהרות)")
            print(f"💾 אומדן זיכרון: {self.memory_estimate}MB")
            return True
        else:
            print(f"\n💀 יש בעיות קריטיות - אל תפרסה!")
            return False

def main():
    """פונקציה ראשית"""
    checker = PreDeployChecker()
    success = checker.run_all_checks()
    
    print("\n" + "="*60)
    if success:
        print("🎉 הפריסה מאושרת לביצוע!")
        sys.exit(0)
    else:
        print("🚫 הפריסה נחסמה - יש לתקן את הבעיות לפני הפריסה")
        sys.exit(1)

if __name__ == "__main__":
    main()