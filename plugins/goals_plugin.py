"""Goals plugin v3."""
import numpy as np
import pandas as pd
import logging
from scipy.stats import norm
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from plugins.base_plugin import BasePlugin
from core.feature_engineering import build_features, engineer_match_features, add_time_weights
from core import model_store

THRESHOLDS = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]

class GoalsPlugin(BasePlugin):
    key = "goals"; name = "Тотал Голов"; emoji = "⚽"; color = "#4A9EFF"; enabled = False
    def __init__(self): super().__init__(); self._std = 1.3

    def train(self, df, league_code=""):
        n = len(df)
        if league_code and not model_store.needs_retrain(self.key, league_code, n):
            model, _ = model_store.load_model(self.key, league_code)
            if model:
                self.model = model; self._trained = True; return
        X, y = build_features(df, "total_goals")
        if X.empty or len(y) < 30: return
        w = add_time_weights(df).reindex(y.index, fill_value=0.2)
        self.model = Pipeline([("imp", SimpleImputer(strategy="median")),
                                ("reg", GradientBoostingRegressor(n_estimators=80, random_state=42))])
        try:
            self.model.fit(X, y, reg__sample_weight=w.values)
            self._trained = True
            if league_code: model_store.save_model(self.model, self.key, league_code, n)
        except Exception as e: logging.error(f"GoalsPlugin train: {e}")

    def predict(self, df_history, home, away, referee=None, league_code=""):
        if not self._trained: self.train(df_history, league_code)
        if not self._trained: return None
        X = engineer_match_features(df_history, home, away, referee)
        if X.empty: return None
        try:
            mean = float(self.model.predict(X)[0])
            out = []
            for t in THRESHOLDS:
                prob = max(0.05, min(0.97, float(1 - norm.cdf(t, mean, self._std))))
                out.append({"value": f"Голы ТБ {t}", "threshold": t, "prob": prob,
                            "label": self._threshold_label(prob)})
            rec_idx = next((j for j, t in enumerate(out) if 0.55 <= t["prob"] <= 0.75), 2)
            rec = out[rec_idx]
            return {"recommendation": rec["value"], "threshold": rec["threshold"],
                    "probability": rec["prob"], "mean_pred": mean, "thresholds": out,
                    "justification": f"Прогнозируемый тотал голов: {mean:.1f}"}
        except Exception as e: logging.error(f"GoalsPlugin predict: {e}"); return None

    def predict_single(self, row): return None
    def get_actual(self, row):
        try: return float(row.get("FTHG", 0) or 0) + float(row.get("FTAG", 0) or 0)
        except: return None
    def evaluate(self, pred, actual): return (pred >= 2.5) == (actual >= 2.5) if pred and actual else False
