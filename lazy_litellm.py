"""
Lazy LiteLLM Wrapper - saves 1GB+ memory!
=========================================

Instead of loading LiteLLM 7 times, load once and share
"""

class LazyLiteLLM:
    """Lazy wrapper for LiteLLM - loads only on first use"""
    
    def __init__(self):
        self._litellm = None
        self._loaded = False
    
    def _ensure_loaded(self):
        """Load LiteLLM only if not loaded yet"""
        if not self._loaded:
            print("Loading LiteLLM for the first time (saving 1GB+ memory)...")
            try:
                import litellm as _litellm  # Real import
                self._litellm = _litellm
                self._loaded = True
                print("LiteLLM loaded successfully!")
            except ImportError as e:
                print(f"[ERROR] Failed to import LiteLLM: {e}")
                raise
    
    def __getattr__(self, name):
        """Forward all functions to real LiteLLM"""
        self._ensure_loaded()
        return getattr(self._litellm, name)
    
    def completion(self, *args, **kwargs):
        """Main function - completion"""
        self._ensure_loaded()
        return self._litellm.completion(*args, **kwargs)
    
    def embedding(self, *args, **kwargs):
        """Embedding function"""
        self._ensure_loaded()
        return self._litellm.embedding(*args, **kwargs)

# Create single global instance
_lazy_litellm_instance = LazyLiteLLM()

# Export all important functions
completion = _lazy_litellm_instance.completion
embedding = _lazy_litellm_instance.embedding

# Export exceptions (if needed)
def __getattr__(name):
    """Forward any other attribute to LiteLLM"""
    return getattr(_lazy_litellm_instance, name) 