"""
Corners Plugin v3 — with model persistence.
"""

import numpy as np
import pandas as pd
import logging
from scipy.stats import norm
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from plugins.base_plugin import BasePlugin
from core.feature_engineering import build_features, engineer_match_features, add_time_weights
from core import model_store

THRESHOLDS = [t / 2 for t in range(13, 32)]  # 6.5 to 15.5


class CornersPlugin(BasePlugin):
    key   = "corners"
    name  = "Угловые"
    emoji = "⛳"
    color = "#00C896"

    def __init__(self):
        super().__init__()
        self._std = 2.5

    def train(self, df: pd.DataFrame, league_code: str = ""):
        n = len(df)
        # Try cached model first
        if league_code and not model_store.needs_retrain(self.key, league_code, n):
            model, _ = model_store.load_model(self.key, league_code)
            if model is not None:
                self.model = model
                self._trained = True
                logging.info(f"CornersPlugin/{league_code}: using cached model")
                return

        X, y = build_features(df, "total_corners")
        if X.empty or len(y) < 30:
            return
        w = add_time_weights(df).reindex(y.index, fill_value=0.2)
        self.model = Pipeline([
            ("imp",   SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("reg",   GradientBoostingRegressor(n_estimators=150, max_depth=4,
                                                learning_rate=0.05, random_state=42)),
        ])
        try:
            self.model.fit(X, y, reg__sample_weight=w.values)
            self._trained = True
            y_hat = self.model.predict(X)
            self._std = float(np.std(y.values - y_hat)) or 2.5
            if league_code:
                model_store.save_model(self.model, self.key, league_code, n)
        except Exception as e:
            logging.error(f"CornersPlugin train: {e}")

    def predict(self, df_history, home, away, referee=None, league_code=""):
        if not self._trained:
            self.train(df_history, league_code)
        if not self._trained:
            return None
        X = engineer_match_features(df_history, home, away, referee)
        if X.empty:
            return None
        try:
            mean = float(self.model.predict(X)[0])
            thresholds_out = []
            for t in THRESHOLDS:
                prob = float(1 - norm.cdf(t, loc=mean, scale=self._std))
                prob = max(0.05, min(0.97, prob))
                thresholds_out.append({"value": f"ТБ {t}", "threshold": t,
                                       "prob": prob, "label": self._threshold_label(prob)})
            # Recommendation: last threshold still ≥ 60%
            rec_idx = max((j for j, t in enumerate(thresholds_out) if t["prob"] >= 0.60),
                          default=0)
            rec = thresholds_out[rec_idx]

            just = self._justify(df_history, home, away, mean)
            return {
                "recommendation": f"{rec['value']} Угловых",
                "threshold": rec["threshold"],
                "probability": rec["prob"],
                "mean_pred": mean,
                "thresholds": thresholds_out,
                "justification": just,
            }
        except Exception as e:
            logging.error(f"CornersPlugin predict: {e}")
            return None

    def predict_single(self, row):
        return None  # Used only in backtesting scaffold

    def get_actual(self, row):
        try:
            return float(row.get("HC", 0) or 0) + float(row.get("AC", 0) or 0)
        except Exception:
            return None

    def evaluate(self, pred, actual):
        return (pred >= 9.5) == (actual >= 9.5)

    def _justify(self, df, home, away, mean):
        lines = []
        for team, side in [(home, "HomeTeam"), (away, "AwayTeam")]:
            m = df[df[side] == team].tail(5)
            if not m.empty and "HC" in m.columns and "AC" in m.columns:
                avg = (m["HC"].fillna(0) + m["AC"].fillna(0)).mean()
                loc = "дома" if side == "HomeTeam" else "на выезде"
                lines.append(f"{team}: {avg:.1f} угл/матч {loc} (посл. 5)")
        lines.append(f"Прогнозируемый тотал: {mean:.1f} угловых")
        return ". ".join(lines) + "."
