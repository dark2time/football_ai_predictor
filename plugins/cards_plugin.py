"""
Cards Plugin v3 — with model persistence and derby detection.
"""

import numpy as np
import pandas as pd
import logging
from scipy.stats import norm
from sklearn.ensemble import RandomForestRegressor
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from plugins.base_plugin import BasePlugin
from core.feature_engineering import build_features, engineer_match_features, add_time_weights
from core import model_store

THRESHOLDS = [t / 2 for t in range(5, 18)]  # 2.5 to 8.5
DERBY_PAIRS = [
    ("Arsenal","Chelsea"),("Arsenal","Tottenham"),("Chelsea","Tottenham"),
    ("Man City","Man United"),("Man City","Liverpool"),("Liverpool","Everton"),
    ("Real Madrid","Barcelona"),("Real Madrid","Atletico"),("Barcelona","Atletico"),
    ("Bayern","Dortmund"),("Inter","Milan"),("Inter","Juventus"),("Milan","Juventus"),
    ("PSG","Marseille"),("Galatasaray","Fenerbahce"),("Galatasaray","Besiktas"),
    ("Benfica","Porto"),("Benfica","Sporting"),("Porto","Sporting"),
]


class CardsPlugin(BasePlugin):
    key   = "cards"
    name  = "Жёлтые Карточки"
    emoji = "🟨"
    color = "#FFD600"

    def __init__(self):
        super().__init__()
        self._std = 1.8

    def train(self, df, league_code=""):
        n = len(df)
        if league_code and not model_store.needs_retrain(self.key, league_code, n):
            model, _ = model_store.load_model(self.key, league_code)
            if model is not None:
                self.model = model
                self._trained = True
                return
        X, y = build_features(df, "total_cards")
        if X.empty or len(y) < 30:
            return
        w = add_time_weights(df).reindex(y.index, fill_value=0.2)
        self.model = Pipeline([
            ("imp",   SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("reg",   RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)),
        ])
        try:
            self.model.fit(X, y, reg__sample_weight=w.values)
            self._trained = True
            y_hat = self.model.predict(X)
            self._std = float(np.std(y.values - y_hat)) or 1.8
            if league_code:
                model_store.save_model(self.model, self.key, league_code, n)
        except Exception as e:
            logging.error(f"CardsPlugin train: {e}")

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
            # Derby modifier
            is_derby = any(
                (h.lower() in home.lower() and a.lower() in away.lower()) or
                (a.lower() in home.lower() and h.lower() in away.lower())
                for h, a in DERBY_PAIRS
            )
            if is_derby:
                mean *= 1.25

            thresholds_out = []
            for t in THRESHOLDS:
                prob = float(1 - norm.cdf(t, loc=mean, scale=self._std))
                prob = max(0.05, min(0.97, prob))
                thresholds_out.append({"value": f"ЖК ТБ {t}", "threshold": t,
                                       "prob": prob, "label": self._threshold_label(prob)})
            rec_idx = max((j for j, t in enumerate(thresholds_out) if t["prob"] >= 0.60),
                          default=0)
            rec = thresholds_out[rec_idx]
            derby_note = " ⚠ Дерби — ожидается больше карточек." if is_derby else ""
            return {
                "recommendation": rec["value"],
                "threshold": rec["threshold"],
                "probability": rec["prob"],
                "mean_pred": mean,
                "thresholds": thresholds_out,
                "justification": f"Прогноз: {mean:.1f} ЖК.{derby_note}",
            }
        except Exception as e:
            logging.error(f"CardsPlugin predict: {e}")
            return None

    def predict_single(self, row): return None
    def get_actual(self, row):
        try:
            return float(row.get("HY", 0) or 0) + float(row.get("AY", 0) or 0)
        except Exception:
            return None
    def evaluate(self, pred, actual):
        return (pred >= 4.5) == (actual >= 4.5) if pred is not None and actual is not None else False
