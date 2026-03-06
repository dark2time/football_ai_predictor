"""
Backtesting v3.2
─────────────────────────────────────────────────────────────
Algorithm:
  train_data  = everything BEFORE (today - 90 days)
  test_window = last 90 days

  1. Train model ONCE on train_data
  2. Loop over test_data matches (no retraining)
  3. Apply value filter: probability >= 0.55, prob*odds >= 1.08
  4. Count bets / wins / losses / ROI

ROI formula:
  win  → profit += odds - 1
  loss → profit -= 1
  ROI  = profit / bets * 100

Incremental cache: data/backtest/{league}_{plugin}.json
  Stores: last_match_date, bets, wins, losses, roi
  On next run: only processes matches after last_match_date

league_stats.json updated after every run.
─────────────────────────────────────────────────────────────
"""

import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta

BACKTEST_DIR   = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "backtest")
LEAGUE_STATS_F = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "league_stats.json")

BACKTEST_DAYS  = 90       # test window
ASSUMED_ODDS   = 1.88     # used when real odds not in CSV
MIN_PROB       = 0.55
MIN_VALUE      = 1.08     # probability * odds


class Backtester:

    def __init__(self):
        os.makedirs(BACKTEST_DIR, exist_ok=True)

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self, df: pd.DataFrame, plugin, league_code: str,
            progress_cb=None) -> dict:
        """
        Run backtest for one plugin on one league.
        Returns: {winrate, roi, total, wins, losses, last_match_date}
        """
        today    = datetime.now()
        test_end  = pd.Timestamp(today - timedelta(days=1))
        test_start = pd.Timestamp(today - timedelta(days=BACKTEST_DAYS))
        train_cut  = test_start   # train on everything before test window

        # ── Load incremental cache ────────────────────────────────────────────
        cache = self._load_cache(league_code, plugin.key)

        if cache and cache.get("last_match_date"):
            last_dt  = pd.Timestamp(cache["last_match_date"])
            # Only new matches since last run
            test_df  = df[(df["Date"] > last_dt) & (df["Date"] <= test_end)].copy()
            base_bets   = cache.get("total",  0)
            base_wins   = cache.get("wins",   0)
            base_losses = cache.get("losses", 0)
            base_profit = cache.get("profit", 0.0)
            logging.info(
                f"Incremental backtest {league_code}/{plugin.key}: "
                f"{len(test_df)} new matches since {str(last_dt)[:10]}"
            )
        else:
            test_df     = df[(df["Date"] >= test_start) & (df["Date"] <= test_end)].copy()
            base_bets   = 0
            base_wins   = 0
            base_losses = 0
            base_profit = 0.0
            logging.info(
                f"Full backtest {league_code}/{plugin.key}: "
                f"{len(test_df)} matches in last {BACKTEST_DAYS} days"
            )

        if len(test_df) < 3:
            if cache:
                self._update_league_stats(league_code, plugin.key, cache)
                return cache
            empty = {"winrate": 0, "roi": 0, "total": 0, "wins": 0,
                     "losses": 0, "profit": 0.0, "last_match_date": None}
            return empty

        test_df = test_df.sort_values("Date").reset_index(drop=True)

        # ── Train model ONCE on data before test window ───────────────────────
        train_df = df[df["Date"] < train_cut].copy()
        if len(train_df) < 50:
            logging.warning(f"Not enough training data for {league_code}/{plugin.key}: {len(train_df)} rows")
            return cache or {"winrate": 0, "roi": 0, "total": 0, "wins": 0,
                             "losses": 0, "profit": 0.0, "last_match_date": None}

        logging.info(f"Training model {league_code}/{plugin.key} on {len(train_df)} matches…")
        if progress_cb:
            progress_cb(61, f"Training {plugin.name}…")

        try:
            # Train without league_code cache — we need a "frozen" snapshot for BT
            plugin.train(train_df, league_code="")
        except Exception as e:
            logging.error(f"BT train failed {league_code}/{plugin.key}: {e}")
            return cache or {"winrate": 0, "roi": 0, "total": 0, "wins": 0,
                             "losses": 0, "profit": 0.0, "last_match_date": None}

        if not plugin._trained:
            logging.warning(f"Plugin {plugin.key} did not train successfully")
            return cache or {"winrate": 0, "roi": 0, "total": 0, "wins": 0,
                             "losses": 0, "profit": 0.0, "last_match_date": None}

        # ── Walk through test matches ─────────────────────────────────────────
        logging.info(f"Backtest window: last {BACKTEST_DAYS} days — {len(test_df)} matches")

        new_bets   = 0
        new_wins   = 0
        new_losses = 0
        new_profit = 0.0
        last_date  = None
        n_total    = len(test_df)

        for i, (_, row) in enumerate(test_df.iterrows()):
            if progress_cb:
                pct = 62 + int(i / n_total * 28)
                progress_cb(pct, f"Backtest {plugin.name}: {i+1}/{n_total}…")

            logging.debug(f"  Testing match {i+1} / {n_total}")

            home = str(row.get("HomeTeam", ""))
            away = str(row.get("AwayTeam", ""))
            if not home or not away:
                continue

            # Actual result
            actual = plugin.get_actual(row)
            if actual is None:
                continue

            # Predict using already-trained model (no retraining)
            try:
                pred = plugin.predict(train_df, home, away,
                                      str(row.get("Referee", "") or ""),
                                      league_code="")
            except Exception as e:
                logging.debug(f"  predict error: {e}")
                continue

            if pred is None:
                continue

            prob      = pred.get("probability", 0)
            threshold = pred.get("threshold")
            if threshold is None:
                continue

            # Get odds from CSV if available, else assume
            odds = _get_odds(row, plugin.key)

            # Value filter
            value = prob * odds
            if prob < MIN_PROB or value < MIN_VALUE:
                continue

            # Evaluate
            correct = actual > threshold   # over bet
            new_bets += 1
            if correct:
                new_wins   += 1
                new_profit += (odds - 1)
                logging.debug(f"  ✅ WIN  | threshold={threshold} actual={actual:.1f} prob={prob:.2f} odds={odds:.2f}")
            else:
                new_losses += 1
                new_profit -= 1
                logging.debug(f"  ❌ LOSS | threshold={threshold} actual={actual:.1f} prob={prob:.2f} odds={odds:.2f}")

            last_date = row["Date"]

        # ── Aggregate ─────────────────────────────────────────────────────────
        total_bets   = base_bets   + new_bets
        total_wins   = base_wins   + new_wins
        total_losses = base_losses + new_losses
        total_profit = base_profit + new_profit

        winrate = (total_wins / total_bets * 100)  if total_bets > 0 else 0.0
        roi     = (total_profit / total_bets * 100) if total_bets > 0 else 0.0

        result = {
            "winrate":         round(winrate, 1),
            "roi":             round(roi, 1),
            "total":           total_bets,
            "wins":            total_wins,
            "losses":          total_losses,
            "profit":          round(total_profit, 2),
            "last_match_date": str(last_date)[:10] if last_date is not None else
                               (cache.get("last_match_date") if cache else None),
        }

        logging.info(
            f"Backtest complete — {league_code} {plugin.key} | "
            f"bets: {total_bets} | wins: {total_wins} | "
            f"winrate: {winrate:.1f}% | ROI: {roi:.1f}%"
        )

        self._save_cache(league_code, plugin.key, result)
        self._update_league_stats(league_code, plugin.key, result)
        return result

    # ── League stats ──────────────────────────────────────────────────────────

    def _update_league_stats(self, league_code: str, plugin_key: str, result: dict):
        stats = {}
        if os.path.exists(LEAGUE_STATS_F):
            try:
                with open(LEAGUE_STATS_F) as f:
                    stats = json.load(f)
            except Exception:
                pass
        if league_code not in stats:
            stats[league_code] = {}
        stats[league_code][plugin_key] = {
            "roi":     result.get("roi", 0),
            "winrate": result.get("winrate", 0),
            "bets":    result.get("total", 0),
        }
        try:
            with open(LEAGUE_STATS_F, "w") as f:
                json.dump(stats, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save league_stats: {e}")

    @staticmethod
    def load_league_stats() -> dict:
        if os.path.exists(LEAGUE_STATS_F):
            try:
                with open(LEAGUE_STATS_F) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _cache_path(self, league_code, plugin_key):
        return os.path.join(BACKTEST_DIR, f"{league_code}_{plugin_key}.json")

    def _load_cache(self, league_code, plugin_key):
        path = self._cache_path(league_code, plugin_key)
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save_cache(self, league_code, plugin_key, data):
        path = self._cache_path(league_code, plugin_key)
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.warning(f"Could not save backtest cache: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_odds(row, plugin_key: str) -> float:
    """Extract bookmaker odds from CSV row if available."""
    try:
        if plugin_key == "corners":
            # football-data.co.uk doesn't have corners odds — use assumed
            return ASSUMED_ODDS
        elif plugin_key == "cards":
            return ASSUMED_ODDS
        elif plugin_key == "goals":
            # Try B365 over 2.5 if available
            val = row.get("B365>2.5") or row.get("BbAv>2.5") or ASSUMED_ODDS
            return float(val) if val and float(val) > 1.0 else ASSUMED_ODDS
        elif plugin_key == "outcome":
            ftr = str(row.get("FTR", ""))
            if ftr == "H":
                v = row.get("B365H") or ASSUMED_ODDS
            elif ftr == "A":
                v = row.get("B365A") or ASSUMED_ODDS
            else:
                v = row.get("B365D") or ASSUMED_ODDS
            return float(v) if v and float(v) > 1.0 else ASSUMED_ODDS
    except Exception:
        pass
    return ASSUMED_ODDS
