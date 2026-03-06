"""Outcome plugin v3."""
import pandas as pd
import logging
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from plugins.base_plugin import BasePlugin
from core.feature_engineering import build_features, engineer_match_features, add_time_weights
from core import model_store

class OutcomePlugin(BasePlugin):
    key = "outcome"; name = "Исход П1/X/П2"; emoji = "🏆"; color = "#FF6B6B"; enabled = False

    def train(self, df, league_code=""):
        if "FTR" not in df.columns: return
        n = len(df)
        if league_code and not model_store.needs_retrain(self.key, league_code, n):
            model, _ = model_store.load_model(self.key, league_code)
            if model:
                self.model = model; self._trained = True; return
        X, y_cont = build_features(df, "total_goals")
        if X.empty: return
        y = df.loc[y_cont.index, "FTR"].fillna("H")
        w = add_time_weights(df).reindex(y.index, fill_value=0.2)
        self.model = Pipeline([("imp", SimpleImputer(strategy="median")),
                                ("scale", StandardScaler()),
                                ("clf", RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1))])
        try:
            self.model.fit(X, y, clf__sample_weight=w.values)
            self._trained = True
            if league_code: model_store.save_model(self.model, self.key, league_code, n)
        except Exception as e: logging.error(f"OutcomePlugin train: {e}")

    def predict(self, df_history, home, away, referee=None, league_code=""):
        if not self._trained: self.train(df_history, league_code)
        if not self._trained: return None
        X = engineer_match_features(df_history, home, away, referee)
        if X.empty: return None
        try:
            proba = self.model.predict_proba(X)[0]
            classes = list(self.model.classes_)
            r = dict(zip(classes, proba))
            p1, draw, p2 = r.get("H",0), r.get("D",0), r.get("A",0)
            best = max(r, key=r.get)
            label = {"H":"П1","D":"X","A":"П2"}.get(best, best)
            return {"recommendation": label, "probability": r[best],
                    "thresholds": [{"value":"П1","prob":p1,"label":self._threshold_label(p1)},
                                   {"value":"X","prob":draw,"label":self._threshold_label(draw)},
                                   {"value":"П2","prob":p2,"label":self._threshold_label(p2)}],
                    "justification": f"П1={p1:.0%}  X={draw:.0%}  П2={p2:.0%}"}
        except Exception as e: logging.error(f"OutcomePlugin predict: {e}"); return None

    def predict_single(self, row): return None
    def get_actual(self, row): return row.get("FTR") if hasattr(row,"get") else None
    def evaluate(self, pred, actual): return pred == actual
