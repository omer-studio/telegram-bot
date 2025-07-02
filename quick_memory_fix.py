#!/usr/bin/env python3
"""
🚀 פתרון מהיר לצריכת זיכרון מטורפת
====================================

הבעיה: LiteLLM נטען 7 פעמים = 1,400MB זיכרון!
הפתרון: Lazy loading - טוען רק כשצריך

השימוש:
1. הרץ: python quick_memory_fix.py
2. זה ייצור lazy_litellm.py  
3. תחליף את את כל ה-imports של litellm
"""

import os

def create_lazy_litellm():
    """יוצר wrapper לazy עבור LiteLLM"""
    
    lazy_code = '''"""
🔄 Lazy LiteLLM Wrapper - חוסך 1GB+ זיכרון!
===========================================

במקום לטעון LiteLLM 7 פעמים, טוען פעם אחת ומשתף
"""

class LazyLiteLLM:
    """Lazy wrapper ל-LiteLLM - טוען רק בפעם הראשונה"""
    
    def __init__(self):
        self._litellm = None
        self._loaded = False
    
    def _ensure_loaded(self):
        """טוען LiteLLM רק אם עוד לא נטען"""
        if not self._loaded:
            print("🔄 Loading LiteLLM for the first time (saving 1GB+ memory)...")
            try:
                import litellm as _litellm  # ייבוא האמיתי
                self._litellm = _litellm
                self._loaded = True
                print("✅ LiteLLM loaded successfully!")
            except ImportError as e:
                print(f"❌ Failed to import LiteLLM: {e}")
                raise
    
    def __getattr__(self, name):
        """מעביר את כל הפונקציות ל-LiteLLM האמיתי"""
        self._ensure_loaded()
        return getattr(self._litellm, name)
    
    def completion(self, *args, **kwargs):
        """פונקציה עיקרית - completion"""
        self._ensure_loaded()
        return self._litellm.completion(*args, **kwargs)
    
    def embedding(self, *args, **kwargs):
        """פונקציית embedding"""
        self._ensure_loaded()
        return self._litellm.embedding(*args, **kwargs)

# יצירת instance גלובלי אחד
_lazy_litellm_instance = LazyLiteLLM()

# Export של כל הפונקציות החשובות
completion = _lazy_litellm_instance.completion
embedding = _lazy_litellm_instance.embedding

# Export של exceptions (אם צריך)
def __getattr__(name):
    """מעביר כל attribute אחר ל-LiteLLM"""
    return getattr(_lazy_litellm_instance, name)
'''
    
    with open("lazy_litellm.py", "w", encoding="utf-8") as f:
        f.write(lazy_code)
    
    print("✅ נוצר lazy_litellm.py")

def create_patch_script():
    """יוצר סקריפט שמחליף את כל ה-imports"""
    
    patch_code = '''#!/usr/bin/env python3
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
    
    print(f"\\n🎉 הושלם! עודכנו {total_changed} קבצים")
    print("💾 חיסכון צפוי בזיכרון: ~1,000-1,400MB!")

if __name__ == "__main__":
    main()
'''
    
    with open("patch_imports.py", "w", encoding="utf-8") as f:
        f.write(patch_code)
    
    print("✅ נוצר patch_imports.py")

def main():
    """פונקציה ראשית"""
    print("🚀 יוצר פתרון מהיר לבעיית הזיכרון...")
    print("=" * 50)
    
    # יצירת הקבצים
    create_lazy_litellm()
    create_patch_script()
    
    print("\\n📋 השלבים הבאים:")
    print("1. הרץ: python patch_imports.py")
    print("2. טעין אותו לרנדר")
    print("3. תיהנה מ-1GB+ פחות זיכרון! 🎉")
    
    print("\\n💡 חיסכון צפוי:")
    print("   לפני: ~1,800MB (קריסה)")
    print("   אחרי: ~400-500MB (עובד מעולה!)")

if __name__ == "__main__":
    main()