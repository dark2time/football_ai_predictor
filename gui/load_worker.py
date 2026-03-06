"""
Load worker v3.1 — PyQt6
- Uses incremental backtesting (365-day window only)
- Passes league_code to plugins for model caching
- AllLeaguesWorker collects TOP VALUE bets
"""

import gc
import logging
import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal

from core.data_loader import DataLoader
from core.backtesting import Backtester
from core.value_filter import passes_filter, value_pct
from plugins.corners_plugin import CornersPlugin
from plugins.cards_plugin import CardsPlugin
from plugins.goals_plugin import GoalsPlugin
from plugins.outcome_plugin import OutcomePlugin

PLUGIN_CLASSES = {
    "corners": CornersPlugin,
    "cards":   CardsPlugin,
    "goals":   GoalsPlugin,
    "outcome": OutcomePlugin,
}

# Default odds used for value filtering when real odds unavailable
ASSUMED_ODDS = 1.88


class LoadWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, league_data: dict, plugin_config: dict):
        super().__init__()
        self.league_data   = league_data
        self.plugin_config = plugin_config
        self._abort        = False

    def abort(self): self._abort = True

    def run(self):
        try:
            code   = self.league_data["code"]
            loader = DataLoader()

            self.progress.emit(5, "Загрузка исторических данных…")
            df = loader.load_league(code, progress_cb=self.progress.emit)
            if df.empty:
                self.error.emit("Нет данных. Проверьте подключение к интернету.")
                return

            plugins    = {}
            backtests  = {}
            backtester = Backtester()

            plugin_order = ["corners", "cards", "goals", "outcome"]
            enabled      = [k for k in plugin_order if self.plugin_config.get(k, {}).get("enabled")]

            for idx, key in enumerate(plugin_order):
                if self._abort: return
                cfg = self.plugin_config.get(key, {})
                cls = PLUGIN_CLASSES.get(key)
                if not cls: continue

                plugin         = cls()
                plugin.enabled = cfg.get("enabled", False)

                if plugin.enabled:
                    base_pct = 55 + idx * 10
                    self.progress.emit(base_pct, f"Обучение: {plugin.name}…")
                    try:
                        plugin.train(df, league_code=code)
                    except Exception as e:
                        logging.warning(f"Train {key}: {e}")

                    self.progress.emit(base_pct + 4, f"Backtest: {plugin.name}…")
                    try:
                        bt = backtester.run(df, plugin, code,
                                            progress_cb=self.progress.emit)
                        plugin.accuracy = bt.get("winrate", 0)
                        plugin.roi      = bt.get("roi", 0)
                        backtests[key]  = bt
                    except Exception as e:
                        logging.warning(f"Backtest {key}: {e}")

                plugins[key] = plugin

            self.progress.emit(93, "Загрузка расписания…")
            fixtures = loader.load_fixtures(code)

            self.progress.emit(100, "Готово!")
            self.finished.emit({
                "df": df, "fixtures": fixtures,
                "plugins": plugins, "backtests": backtests,
                "league": self.league_data,
            })
        except Exception as e:
            logging.exception("LoadWorker error")
            self.error.emit(str(e))


class AllLeaguesWorker(QThread):
    """Pre-loads all leagues and collects TOP VALUE bets."""
    progress    = pyqtSignal(int, str)
    league_done = pyqtSignal(str, dict)
    finished    = pyqtSignal(list)   # emits top_value list
    error       = pyqtSignal(str)

    def __init__(self, leagues: list, plugin_config: dict):
        super().__init__()
        self.leagues       = leagues
        self.plugin_config = plugin_config
        self._abort        = False

    def abort(self): self._abort = True

    def run(self):
        loader     = DataLoader()
        backtester = Backtester()
        total      = len(self.leagues)
        all_value_bets = []

        for li, lg in enumerate(self.leagues):
            if self._abort: return
            code = lg["code"]
            base = int(li / total * 90)
            self.progress.emit(base, f"Загружаю {lg['league']}…")

            try:
                df = loader.load_league(code)
                if df.empty:
                    continue

                plugins = {}
                for key in ["corners", "cards"]:
                    cfg = self.plugin_config.get(key, {})
                    cls = PLUGIN_CLASSES.get(key)
                    if not cls: continue
                    p = cls(); p.enabled = True
                    try:
                        p.train(df, league_code=code)
                        bt = backtester.run(df, p, code)
                        p.accuracy = bt.get("winrate", 0)
                        p.roi      = bt.get("roi", 0)
                    except Exception as e:
                        logging.warning(f"AllLeagues {code}/{key}: {e}")
                    plugins[key] = p

                fixtures = loader.load_fixtures(code)

                payload = {
                    "df": df, "fixtures": fixtures,
                    "plugins": plugins, "league": lg,
                }
                self.league_done.emit(code, payload)

                # Collect value bets from this league's fixtures
                if not fixtures.empty:
                    bets = _collect_value_bets(df, fixtures, plugins, lg)
                    all_value_bets.extend(bets)

            except Exception as e:
                logging.warning(f"AllLeagues {code}: {e}")

        # Sort by value descending, take top 10
        all_value_bets.sort(key=lambda x: x["value"], reverse=True)
        self.progress.emit(100, "Все лиги загружены!")
        self.finished.emit(all_value_bets[:10])


def _collect_value_bets(df, fixtures, plugins, lg) -> list:
    """Generate value bet candidates from upcoming fixtures."""
    results = []
    code    = lg.get("code", "")

    for _, row in fixtures.head(15).iterrows():
        home = str(row.get("HomeTeam", ""))
        away = str(row.get("AwayTeam", ""))
        if not home or not away:
            continue

        for key in ["corners", "cards"]:
            p = plugins.get(key)
            if p is None or not p.enabled:
                continue
            try:
                pred = p.predict(df, home, away, league_code=code)
                if pred is None:
                    continue

                prob  = pred.get("probability", 0)
                value = prob * ASSUMED_ODDS   # value = prob * odds

                if passes_filter(prob, ASSUMED_ODDS):
                    date_str = str(row.get("Date", ""))[:10]
                    results.append({
                        "match":       f"{home} – {away}",
                        "market":      pred.get("recommendation", "—"),
                        "probability": prob,
                        "odds":        ASSUMED_ODDS,
                        "value":       value,
                        "value_pct":   value_pct(prob, ASSUMED_ODDS),
                        "league":      lg.get("league", ""),
                        "league_code": code,
                        "date":        date_str,
                    })
            except Exception as e:
                logging.debug(f"Value bet collect {code}/{key}: {e}")

    return results
