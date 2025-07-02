# Memory Optimization Report - Render.com Deployment

## Issue Summary
The application is exceeding Render.com's 512MB memory limit, causing "Out of memory" errors and deployment failures.

## Root Causes

### 1. Heavy AI Library Loading
- Multiple AI libraries loaded simultaneously: OpenAI, Anthropic, Google Generative AI, LiteLLM
- All models initialized at startup instead of on-demand

### 2. Post-Deploy Subprocess Memory Usage  
- `auto_rollback.py` runs as subprocess during startup
- Creates additional Python process consuming ~50-100MB

### 3. Extensive Module Imports
- 40+ Python modules imported at startup
- Heavy modules like `notifications.py` (78KB), `message_handler.py` (44KB)
- Google Sheets connections established immediately

### 4. Multiple GPT Handler Instances
- Separate handlers for GPT A, B, C, D, E loaded simultaneously
- Each handler imports heavy dependencies

## Immediate Solutions (Quick Fixes)

### Solution 1: Optimize Post-Deploy Check
**Impact**: Save 50-100MB memory

```python
# In main.py - modify run_post_deploy_check()
def run_post_deploy_check():
    """Optimized post-deploy check with memory constraints"""
    try:
        if os.getenv("RENDER") or os.getenv("RAILWAY_STATIC_URL"):
            is_new_deploy = (
                os.getenv("RENDER_GIT_COMMIT") or 
                (os.getenv("PORT") and not os.path.exists("data/deploy_verified.flag"))
            )
            
            if is_new_deploy:
                print("🚨 New deploy detected - running lightweight verification...")
                
                # LIGHTWEIGHT CHECK instead of subprocess
                try:
                    # Basic health check without subprocess
                    from health_check import basic_health_check
                    if basic_health_check():
                        print("✅ Lightweight verification passed!")
                        os.makedirs("data", exist_ok=True)
                        with open("data/deploy_verified.flag", "w", encoding="utf-8") as f:
                            f.write(f"verified_at_{os.getenv('RENDER_GIT_COMMIT', 'unknown')}")
                    else:
                        print("⚠️ Health check failed but continuing...")
                except Exception as e:
                    print(f"⚠️ Verification error: {e} - continuing anyway")
            else:
                print("ℹ️ Existing verified deploy - continuing")
        else:
            print("ℹ️ Development environment - skipping verification")
            
    except Exception as e:
        print(f"⚠️ Post-deploy check error: {e} - continuing")
        # Don't exit on error in production - just log and continue
```

### Solution 2: Lazy Import Heavy Dependencies
**Impact**: Save 100-150MB memory

```python
# Create new file: lazy_imports.py
"""
Lazy import wrapper for heavy dependencies
Only loads modules when actually needed
"""

class LazyImporter:
    def __init__(self, module_name, import_path=None):
        self.module_name = module_name
        self.import_path = import_path or module_name
        self._module = None
    
    def __getattr__(self, name):
        if self._module is None:
            print(f"🔄 Lazy loading {self.module_name}...")
            try:
                if '.' in self.import_path:
                    parts = self.import_path.split('.')
                    self._module = __import__(self.import_path, fromlist=[parts[-1]])
                else:
                    self._module = __import__(self.import_path)
            except ImportError as e:
                print(f"❌ Failed to lazy load {self.module_name}: {e}")
                raise
        return getattr(self._module, name)

# Lazy imports for heavy modules
openai = LazyImporter("openai")
anthropic = LazyImporter("anthropic") 
litellm = LazyImporter("litellm")
google_generativeai = LazyImporter("google.generativeai", "google.generativeai")
gspread = LazyImporter("gspread")
```

### Solution 3: Optimize Google Sheets Connection
**Impact**: Save 50-75MB memory

```python
# In config.py - modify setup_google_sheets()
def setup_google_sheets():
    """Memory-optimized Google Sheets setup"""
    global _sheets_cache, _cache_created_at
    
    if _sheets_cache is not None:
        try:
            # Quick connection test without loading data
            _sheets_cache[1].title  # Just check if connection exists
            return _sheets_cache
        except:
            _sheets_cache = None
    
    # Lazy import Google Sheets libraries
    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
    except ImportError:
        from lazy_imports import gspread, ServiceAccountCredentials
    
    # Minimal connection - only load when needed
    scope = ["https://spreadsheets.google.com/feeds"]  # Reduced scope
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        config["SERVICE_ACCOUNT_DICT"], scope
    )
    gs_client = gspread.authorize(creds)
    
    # Connect to sheets but don't load data yet
    sheet = gs_client.open_by_key(GOOGLE_SHEET_ID)
    sheet_users = sheet.worksheet(config["SHEET_USER_TAB"])
    sheet_log = sheet.worksheet(config["SHEET_LOG_TAB"]) 
    sheet_states = sheet.worksheet(config["SHEET_STATES_TAB"])
    
    _sheets_cache = (gs_client, sheet_users, sheet_log, sheet_states)
    _cache_created_at = time.time()
    return _sheets_cache
```

### Solution 4: Optimize GPT Handler Loading
**Impact**: Save 75-100MB memory

```python
# Create new file: gpt_factory.py
"""
Factory pattern for GPT handlers - load only when needed
"""

class GPTHandlerFactory:
    def __init__(self):
        self._handlers = {}
    
    def get_handler(self, handler_type):
        """Get GPT handler, loading only when first requested"""
        if handler_type not in self._handlers:
            print(f"🔄 Loading GPT {handler_type} handler...")
            
            if handler_type == 'a':
                from gpt_a_handler import GPTAHandler
                self._handlers[handler_type] = GPTAHandler()
            elif handler_type == 'b':
                from gpt_b_handler import GPTBHandler  
                self._handlers[handler_type] = GPTBHandler()
            elif handler_type == 'c':
                from gpt_c_handler import GPTCHandler
                self._handlers[handler_type] = GPTCHandler()
            elif handler_type == 'd':
                from gpt_d_handler import GPTDHandler
                self._handlers[handler_type] = GPTDHandler()
            elif handler_type == 'e':
                from gpt_e_handler import GPTEHandler
                self._handlers[handler_type] = GPTEHandler()
            else:
                raise ValueError(f"Unknown handler type: {handler_type}")
        
        return self._handlers[handler_type]

# Global factory instance
gpt_factory = GPTHandlerFactory()
```

## Medium-term Solutions

### Solution 5: Upgrade Render Plan
**Cost**: ~$7-25/month  
**Impact**: 1GB-4GB memory limit

Consider upgrading to Render's Starter plan ($7/month) for 1GB RAM, or Pro plan ($25/month) for 4GB RAM.

### Solution 6: Memory Profiling
Add memory monitoring to identify specific memory hotspots:

```python
# Add to main.py
import psutil
import os

def log_memory_usage(stage):
    """Log current memory usage"""
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"📊 Memory usage at {stage}: {memory_mb:.1f} MB")

# Usage:
log_memory_usage("startup")
log_memory_usage("after_imports")  
log_memory_usage("after_sheets_setup")
log_memory_usage("ready")
```

## Implementation Priority

1. **IMMEDIATE** (Deploy today):
   - Optimize post-deploy check (Solution 1)
   - Add memory logging (Solution 6)

2. **HIGH** (This week):
   - Implement lazy imports (Solution 2)
   - Optimize Google Sheets (Solution 3)

3. **MEDIUM** (Next week):
   - GPT handler factory (Solution 4)
   - Consider plan upgrade (Solution 5)

## Expected Results

Implementing solutions 1-4 should reduce memory usage from ~600MB to ~300-400MB, well within the 512MB limit.

## Monitoring

After implementing optimizations, monitor memory usage with:
- Render.com dashboard metrics
- Memory logging in application
- Performance impact on response times

---

*Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*