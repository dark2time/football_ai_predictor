"""
Automatically checks pending bets against fresh CSV data.
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from core.data_loader import DataLoader


def auto_check_results(db) -> dict:
    """
    Check all pending bets against downloaded CSV data.
    Returns summary: { checked, won, lost, bank_delta }
    """
    pending = db.get_pending_bets()
    if not pending:
        return {"checked": 0, "won": 0, "lost": 0, "bank_delta": 0}

    loader = DataLoader()
    leagues = list(set(b["league"] for b in pending))
    league_dfs = {}
    for lg in leagues:
        try:
            df = loader.load_league(lg)
            if not df.empty:
                league_dfs[lg] = df
        except Exception as e:
            logging.warning(f"Could not load {lg} for auto-check: {e}")

    summary = {"checked": 0, "won": 0, "lost": 0, "bank_delta": 0}
    bank_before = db.get_bankroll()["amount"]

    for bet in pending:
        lg = bet["league"]
        if lg not in league_dfs:
            continue

        df = league_dfs[lg]
        bet_date = pd.to_datetime(bet["date"])

        # Find the match in the CSV (by date ±2 days and team names)
        match_str = bet["match"]  # "HomeTeam vs AwayTeam"
        parts = match_str.split(" vs ")
        if len(parts) != 2:
            continue
        home, away = parts

        mask = (
            (df["Date"] >= bet_date - timedelta(days=2)) &
            (df["Date"] <= bet_date + timedelta(days=2))
        )
        if "HomeTeam" in df.columns:
            mask &= df["HomeTeam"].str.contains(home.split()[0], case=False, na=False)
        if "AwayTeam" in df.columns:
            mask &= df["AwayTeam"].str.contains(away.split()[0], case=False, na=False)

        found = df[mask]
        if found.empty:
            continue  # Not yet in CSV

        row = found.iloc[0]
        forecast = bet["forecast"]  # e.g. "ТБ 9.5 угл" or "ЖК ТБ 4.5"

        correct = _evaluate_forecast(forecast, row)
        if correct is None:
            continue

        result = "won" if correct else "lost"
        db.update_bet_result(bet["id"], result)
        summary["checked"] += 1
        if correct:
            summary["won"] += 1
        else:
            summary["lost"] += 1
        logging.info(f"Auto-checked bet {bet['id']}: {result}")

    bank_after = db.get_bankroll()["amount"]
    summary["bank_delta"] = bank_after - bank_before
    return summary


def _evaluate_forecast(forecast: str, row) -> bool | None:
    """Parse forecast string and compare with actual match data."""
    forecast = forecast.upper()
    try:
        if "УГЛ" in forecast or "CORNER" in forecast:
            actual = float(row.get("HC", 0) or 0) + float(row.get("AC", 0) or 0)
            threshold = _extract_threshold(forecast)
            if threshold is None:
                return None
            if "ТБ" in forecast or "OVER" in forecast:
                return actual > threshold
            else:
                return actual < threshold

        elif "ЖК" in forecast or "CARD" in forecast or "КАР" in forecast:
            actual = float(row.get("HY", 0) or 0) + float(row.get("AY", 0) or 0)
            threshold = _extract_threshold(forecast)
            if threshold is None:
                return None
            if "ТБ" in forecast or "OVER" in forecast:
                return actual > threshold
            else:
                return actual < threshold

        elif "ГОЛЫ" in forecast or "GOAL" in forecast:
            actual = float(row.get("FTHG", 0) or 0) + float(row.get("FTAG", 0) or 0)
            threshold = _extract_threshold(forecast)
            if threshold is None:
                return None
            if "ТБ" in forecast or "OVER" in forecast:
                return actual > threshold
            else:
                return actual < threshold

        elif "П1" in forecast or "П2" in forecast or "X" in forecast:
            ftr = row.get("FTR", "")
            if "П1" in forecast:
                return ftr == "H"
            elif "П2" in forecast:
                return ftr == "A"
            elif "НИЧЬЯ" in forecast or forecast.strip() == "X":
                return ftr == "D"

    except Exception as e:
        logging.debug(f"Forecast evaluation error: {e}")
    return None


def _extract_threshold(s: str) -> float | None:
    import re
    nums = re.findall(r"\d+\.?\d*", s)
    if nums:
        return float(nums[-1])
    return None
