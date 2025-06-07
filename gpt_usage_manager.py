"""
gpt_usage_manager.py
-------------------
מחלקה מרכזית לניהול usage/עלות GPT, כולל טעינת מחירון, חישוב usage אחיד, ו-fallback חכם.
כל החישובים בקוד יעברו דרך מחלקה זו בלבד.
"""
import os
import json
from typing import List

class GPTUsageManager:
    def __init__(self, pricing_path=None):
        """
        אתחול: טוען את המחירון פעם אחת בלבד.
        """
        if pricing_path is None:
            pricing_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gpt_pricing.json')
        self.pricing = self._load_pricing(pricing_path)
        self.usd_to_ils = 3.7  # ניתן לעדכן דינאמית

    def _load_pricing(self, path):
        """
        טוען את קובץ המחירון (JSON) ומחזיר dict. במקרה של שגיאה – מחזיר dict ריק.
        """
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[GPTUsageManager] שגיאה בטעינת מחירון: {e}")
            return {}

    def _get_model_prices(self, model_name):
        """
        מחזיר את מחירי הטוקנים למודל (prompt/cached/completion) או None אם לא קיים.
        מבצע normalization לשם המודל (למשל gpt-4o-2024-08-06 -> gpt-4o).
        """
        if not model_name:
            return None
        base_name = model_name.split("-")[0]
        if model_name in self.pricing:
            return self.pricing[model_name]
        for key in self.pricing:
            if model_name.startswith(key):
                return self.pricing[key]
        if base_name in self.pricing:
            return self.pricing[base_name]
        print(f"[GPTUsageManager] לא נמצא מחירון למודל: {model_name}")
        return None

    def calculate(self, model_name, prompt_tokens, completion_tokens, cached_tokens=0, usd_to_ils=None):
        """
        מחשב usage+עלות למודל מסוים. תמיד מחזיר dict usage עם כל השדות (גם אם הערך 0).
        אם המודל לא קיים – fallback לערכים 0.
        """
        if usd_to_ils is None:
            usd_to_ils = self.usd_to_ils
        prompt_regular = prompt_tokens - cached_tokens
        prices = self._get_model_prices(model_name)
        if not prices:
            # fallback: usage ריק עם כל השדות
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cached_tokens": cached_tokens,
                "prompt_regular": prompt_regular,
                "cost_prompt_regular": 0.0,
                "cost_prompt_cached": 0.0,
                "cost_completion": 0.0,
                "cost_total": 0.0,
                "cost_total_ils": 0.0,
                "cost_agorot": 0,
                "model": model_name or ""
            }
        cost_prompt_regular = prompt_regular * prices["prompt"]
        cost_prompt_cached = cached_tokens * prices["cached"]
        cost_completion = completion_tokens * prices["completion"]
        cost_total = cost_prompt_regular + cost_prompt_cached + cost_completion
        cost_total_ils = round(cost_total * usd_to_ils, 4)
        cost_agorot = int(round(cost_total_ils * 100))
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_tokens": cached_tokens,
            "prompt_regular": prompt_regular,
            "cost_prompt_regular": cost_prompt_regular,
            "cost_prompt_cached": cost_prompt_cached,
            "cost_completion": cost_completion,
            "cost_total": cost_total,
            "cost_total_ils": cost_total_ils,
            "cost_agorot": cost_agorot,
            "model": model_name or ""
        }

    def merge_usages(self, usages: List[dict]) -> dict:
        """
        מאחד רשימות usage (למשל לדוח/שורה) – סכום טוקנים, עלות, וכו'.
        תמיד מחזיר usage אחיד.
        """
        fields = [
            "prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "prompt_regular",
            "cost_prompt_regular", "cost_prompt_cached", "cost_completion", "cost_total", "cost_total_ils", "cost_agorot"
        ]
        result = {k: 0 for k in fields}
        models = []
        for usage in usages:
            for k in fields:
                result[k] += usage.get(k, 0)
            if usage.get("model"):
                models.append(usage["model"])
        result["model"] = ",".join(models)
        return result 