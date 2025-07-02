#!/usr/bin/env python3
"""
🔧 מחליף את כל ה-imports של LiteLLM ב-lazy version
==============================================
"""

import os
import re

def patch_file(filepath):
    """מחליף import litellm ב-lazy version"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # חיפוש והחלפה של imports
        original_imports = [
            "import litellm",
            "from litellm import completion",
            "from litellm import embedding"
        ]
        
        new_imports = [
            "import lazy_litellm as litellm",
            "from lazy_litellm import completion", 
            "from lazy_litellm import embedding"
        ]
        
        changed = False
        for old, new in zip(original_imports, new_imports):
            if old in content:
                content = content.replace(old, new)
                changed = True
                print(f"📝 {filepath}: {old} -> {new}")
        
        if changed:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"✅ עודכן: {filepath}")
        
        return changed
    
    except Exception as e:
        print(f"❌ שגיאה ב-{filepath}: {e}")
        return False

def main():
    """מחליף imports בכל הקבצים הרלוונטיים"""
    files_to_patch = [
        "gpt_a_handler.py",
        "gpt_b_handler.py", 
        "gpt_c_handler.py",
        "gpt_d_handler.py",
        "gpt_e_handler.py",
        "gpt_utils.py",
        "chat_utils.py"
    ]
    
    print("🔧 מתחיל להחליף imports...")
    
    total_changed = 0
    for filepath in files_to_patch:
        if os.path.exists(filepath):
            if patch_file(filepath):
                total_changed += 1
        else:
            print(f"⚠️ קובץ לא נמצא: {filepath}")
    
    print(f"\n🎉 הושלם! עודכנו {total_changed} קבצים")
    print("💾 חיסכון צפוי בזיכרון: ~1,000-1,400MB!")

if __name__ == "__main__":
    main()
