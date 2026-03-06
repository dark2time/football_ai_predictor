"""Base plugin interface v3."""
import pandas as pd
import gc
import logging
from abc import ABC, abstractmethod


class BasePlugin(ABC):
    key     = "base"
    name    = "Base"
    emoji   = "🔌"
    color   = "#888"
    enabled = True

    def __init__(self):
        self.model    = None
        self.accuracy = 0.0
        self.roi      = 0.0
        self._trained = False

    @abstractmethod
    def train(self, df: pd.DataFrame, league_code: str = ""): pass

    @abstractmethod
    def predict(self, df_history, home, away, referee=None, league_code="") -> dict | None: pass

    @abstractmethod
    def predict_single(self, row) -> float | None: pass

    @abstractmethod
    def get_actual(self, row) -> float | None: pass

    def evaluate(self, pred, actual) -> bool:
        return pred == actual

    def _threshold_label(self, prob: float) -> str:
        if prob >= 0.75:  return "Безопасно"
        if prob >= 0.60:  return "Умеренно"
        if prob >= 0.45:  return "Риск"
        return "Высокий риск"

    def get_stats(self) -> dict:
        return {"key": self.key, "name": self.name, "emoji": self.emoji,
                "color": self.color, "enabled": self.enabled,
                "accuracy": round(self.accuracy, 1), "roi": round(self.roi, 1)}

    def unload(self):
        self.model = None
        self._trained = False
        gc.collect()
