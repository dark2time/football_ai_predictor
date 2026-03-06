"""
Model persistence — save/load trained sklearn models with joblib.
Implements incremental retraining when new data is available.
"""

import os
import logging
import joblib
from datetime import datetime, timedelta

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "models")


def model_path(plugin_key: str, league_code: str) -> str:
    os.makedirs(MODELS_DIR, exist_ok=True)
    return os.path.join(MODELS_DIR, f"{plugin_key}_{league_code}.pkl")


def meta_path(plugin_key: str, league_code: str) -> str:
    return model_path(plugin_key, league_code).replace(".pkl", "_meta.json")


def save_model(model, plugin_key: str, league_code: str, n_samples: int):
    import json
    path = model_path(plugin_key, league_code)
    try:
        joblib.dump(model, path, compress=3)
        meta = {
            "trained_at": datetime.now().isoformat(),
            "n_samples": n_samples,
            "plugin": plugin_key,
            "league": league_code,
        }
        with open(meta_path(plugin_key, league_code), "w") as f:
            json.dump(meta, f)
        logging.info(f"Model saved: {plugin_key}/{league_code} ({n_samples} samples)")
    except Exception as e:
        logging.warning(f"Could not save model: {e}")


def load_model(plugin_key: str, league_code: str):
    """Returns (model, meta) or (None, None)."""
    import json
    path = model_path(plugin_key, league_code)
    if not os.path.exists(path):
        return None, None
    try:
        model = joblib.load(path)
        meta = {}
        mp = meta_path(plugin_key, league_code)
        if os.path.exists(mp):
            with open(mp) as f:
                meta = json.load(f)
        return model, meta
    except Exception as e:
        logging.warning(f"Could not load model {plugin_key}/{league_code}: {e}")
        return None, None


def needs_retrain(plugin_key: str, league_code: str, current_n_samples: int,
                  max_age_days: int = 30) -> bool:
    """True if model doesn't exist, is too old, or has significantly fewer samples."""
    _, meta = load_model(plugin_key, league_code)
    if meta is None:
        return True

    # Age check
    trained_at = datetime.fromisoformat(meta.get("trained_at", "2000-01-01"))
    if (datetime.now() - trained_at).days > max_age_days:
        logging.info(f"Model {plugin_key}/{league_code} is older than {max_age_days} days — retraining")
        return True

    # New data check: retrain if >100 new samples
    old_n = meta.get("n_samples", 0)
    if current_n_samples - old_n > 100:
        logging.info(f"Model {plugin_key}/{league_code}: {current_n_samples - old_n} new samples — retraining")
        return True

    return False
