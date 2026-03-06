"""
Feature Engineering v3.2
─────────────────────────────────────────────────────────────
Season-based sample weights (used via add_time_weights()):

  current season      → 1.0
  1 season ago        → 0.9
  2 seasons ago       → 0.75
  3 seasons ago       → 0.6
  4–6 seasons ago     → 0.4
  older than 6 seasons → 0.2

Features added in v3.1:
  corner_pace_last5 / corner_pace_last10
  (total corners in match for each team, rolling avg)
─────────────────────────────────────────────────────────────
"""

import pandas as pd
import numpy as np
from datetime import datetime


# ── Season helpers ────────────────────────────────────────────────────────────

def _current_season_start_year() -> int:
    """July = new season starts. Returns year the current season started."""
    now = datetime.now()
    return now.year if now.month >= 7 else now.year - 1


def _season_age(match_date: pd.Timestamp) -> int:
    """How many seasons ago did this match happen? 0 = current season."""
    cur = _current_season_start_year()
    match_year = match_date.year if match_date.month >= 7 else match_date.year - 1
    return max(0, cur - match_year)


def add_time_weights(df: pd.DataFrame) -> pd.Series:
    """
    Returns a Series of sample weights based on season age.
    Newer seasons get higher weight.
    """
    weights = pd.Series(0.2, index=df.index, dtype=float)
    if "Date" not in df.columns:
        return weights

    dates = pd.to_datetime(df["Date"], errors="coerce")

    # Vectorised season-age calculation
    # Season start year = year if month>=7, else year-1
    match_season_year = dates.dt.year.where(dates.dt.month >= 7, dates.dt.year - 1)
    cur = _current_season_start_year()
    age = (cur - match_season_year).clip(lower=0)

    weights[age == 0] = 1.0
    weights[age == 1] = 0.9
    weights[age == 2] = 0.75
    weights[age == 3] = 0.6
    weights[(age >= 4) & (age <= 6)] = 0.4
    weights[age > 6]  = 0.2

    return weights


# ── Target derivation ─────────────────────────────────────────────────────────

def _derive_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "HC" in df.columns and "AC" in df.columns:
        df["total_corners"] = df["HC"].fillna(0).astype(float) + df["AC"].fillna(0).astype(float)
    if "HY" in df.columns and "AY" in df.columns:
        df["total_cards"]   = df["HY"].fillna(0).astype(float) + df["AY"].fillna(0).astype(float)
    if "FTHG" in df.columns and "FTAG" in df.columns:
        df["total_goals"]   = df["FTHG"].fillna(0).astype(float) + df["FTAG"].fillna(0).astype(float)
    return df


# ── Feature building ──────────────────────────────────────────────────────────

def build_features(df: pd.DataFrame, target: str):
    """
    Build (X, y) for supervised training.
    Uses ALL rows (no train/test split here — caller controls that).
    Returns (pd.DataFrame, pd.Series).
    """
    df = _derive_targets(df)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    rows, targets = [], []
    for i in range(len(df)):
        if i < 10:
            continue
        row  = df.iloc[i]
        past = df.iloc[:i]
        feat = _extract(past, row)
        if feat and target in df.columns and not pd.isna(df.at[i, target]):
            rows.append(feat)
            targets.append(float(df.at[i, target]))

    if not rows:
        return pd.DataFrame(), pd.Series(dtype=float)
    return pd.DataFrame(rows), pd.Series(targets, dtype=float)


def engineer_match_features(df: pd.DataFrame, home: str, away: str,
                              referee: str = None) -> pd.DataFrame:
    """Build a single feature row for an upcoming match."""
    df = _derive_targets(df)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)

    class _Row:
        def __init__(self, d):  self._d = d
        def get(self, k, dfl=None): return self._d.get(k, dfl)

    fake = _Row({"HomeTeam": home, "AwayTeam": away,
                 "Date": pd.Timestamp.now(), "Referee": referee or ""})
    feat = _extract(df, fake)
    return pd.DataFrame([feat]) if feat else pd.DataFrame()


# ── Feature extractor ─────────────────────────────────────────────────────────

def _extract(past: pd.DataFrame, row) -> dict | None:
    home = row.get("HomeTeam", "")
    away = row.get("AwayTeam", "")
    if not home or not away or len(past) < 5:
        return None

    feat = {}

    def rolling(team, col, n, home_side: bool) -> float:
        if col not in past.columns:
            return 0.0
        mask = (past["HomeTeam"] == team) if home_side else (past["AwayTeam"] == team)
        vals = past[mask][col].dropna().tail(n)
        return float(vals.mean()) if len(vals) > 0 else 0.0

    # ── Standard rolling averages ─────────────────────────────────────────────
    for col in ["total_corners", "total_cards", "total_goals"]:
        for n in [5, 10]:
            feat[f"h_{col}_{n}"] = rolling(home, col, n, True)
            feat[f"a_{col}_{n}"] = rolling(away, col, n, False)

    # ── Corner pace (v3.1) ────────────────────────────────────────────────────
    # corner_pace = total corners in the match (for + against) — per team
    if "HC" in past.columns and "AC" in past.columns:
        for n in [5, 10]:
            hm = past[past["HomeTeam"] == home].tail(n)
            feat[f"h_corner_pace_{n}"] = float(
                (hm["HC"].fillna(0) + hm["AC"].fillna(0)).mean()
            ) if not hm.empty else 0.0

            am = past[past["AwayTeam"] == away].tail(n)
            feat[f"a_corner_pace_{n}"] = float(
                (am["HC"].fillna(0) + am["AC"].fillna(0)).mean()
            ) if not am.empty else 0.0

            feat[f"combined_corner_pace_{n}"] = (
                feat[f"h_corner_pace_{n}"] + feat[f"a_corner_pace_{n}"]
            ) / 2.0

    # ── H2H ──────────────────────────────────────────────────────────────────
    h2h = past[
        ((past["HomeTeam"] == home) & (past["AwayTeam"] == away)) |
        ((past["HomeTeam"] == away) & (past["AwayTeam"] == home))
    ].tail(5)
    for col in ["total_corners", "total_cards"]:
        if col in past.columns:
            feat[f"h2h_{col}"] = float(h2h[col].mean()) if not h2h.empty else 0.0

    # ── Win rate ──────────────────────────────────────────────────────────────
    if "FTR" in past.columns:
        hm5 = past[past["HomeTeam"] == home].tail(5)
        feat["h_winrate"] = float((hm5["FTR"] == "H").sum() / max(len(hm5), 1))
        am5 = past[past["AwayTeam"] == away].tail(5)
        feat["a_winrate"] = float((am5["FTR"] == "A").sum() / max(len(am5), 1))

    # ── Referee ───────────────────────────────────────────────────────────────
    ref = row.get("Referee", "")
    if ref and "Referee" in past.columns and "total_cards" in past.columns:
        rm = past[past["Referee"] == ref]
        feat["ref_avg_cards"] = float(rm["total_cards"].mean()) if not rm.empty else 0.0

    feat["month"] = datetime.now().month
    return feat
