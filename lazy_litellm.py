"""
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
