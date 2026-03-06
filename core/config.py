"""
Configuration v1.0 — 18 leagues, country grouping, league enable/disable,
app update system, data path separation.
"""

import json
import os
import logging

APP_DIR  = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")

# Settings file (user preferences, league on/off)
SETTINGS_PATH    = os.path.join(DATA_DIR, "settings.json")
CONFIG_PATH      = os.path.join(APP_DIR, "config.json")

# ── All 18 supported leagues grouped by country ───────────────────────────────
ALL_LEAGUES = [
    # England
    {"code": "E0",  "country": "England",     "country_flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "league": "Premier League",  "color": "#CC0000"},
    {"code": "E1",  "country": "England",     "country_flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "league": "Championship",    "color": "#CC0000"},
    {"code": "E2",  "country": "England",     "country_flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "league": "League One",      "color": "#CC0000"},
    {"code": "E3",  "country": "England",     "country_flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "league": "League Two",      "color": "#CC0000"},
    # Scotland
    {"code": "SC0", "country": "Scotland",    "country_flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "league": "Premiership",     "color": "#003399"},
    {"code": "SC1", "country": "Scotland",    "country_flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "league": "Championship",    "color": "#003399"},
    # Germany
    {"code": "D1",  "country": "Germany",     "country_flag": "🇩🇪", "league": "Bundesliga",      "color": "#DD0000"},
    {"code": "D2",  "country": "Germany",     "country_flag": "🇩🇪", "league": "Bundesliga 2",    "color": "#DD0000"},
    # Italy
    {"code": "I1",  "country": "Italy",       "country_flag": "🇮🇹", "league": "Serie A",         "color": "#0066CC"},
    {"code": "I2",  "country": "Italy",       "country_flag": "🇮🇹", "league": "Serie B",         "color": "#0066CC"},
    # Spain
    {"code": "SP1", "country": "Spain",       "country_flag": "🇪🇸", "league": "La Liga",         "color": "#AA151B"},
    {"code": "SP2", "country": "Spain",       "country_flag": "🇪🇸", "league": "Segunda",         "color": "#AA151B"},
    # France
    {"code": "F1",  "country": "France",      "country_flag": "🇫🇷", "league": "Ligue 1",         "color": "#002395"},
    {"code": "F2",  "country": "France",      "country_flag": "🇫🇷", "league": "Ligue 2",         "color": "#002395"},
    # Netherlands
    {"code": "N1",  "country": "Netherlands", "country_flag": "🇳🇱", "league": "Eredivisie",      "color": "#FF6600"},
    # Belgium
    {"code": "B1",  "country": "Belgium",     "country_flag": "🇧🇪", "league": "Pro League",      "color": "#EF3340"},
    # Portugal
    {"code": "P1",  "country": "Portugal",    "country_flag": "🇵🇹", "league": "Primeira Liga",   "color": "#006600"},
    # Turkey
    {"code": "T1",  "country": "Turkey",      "country_flag": "🇹🇷", "league": "Süper Lig",       "color": "#E30A17"},
    # Greece
    {"code": "G1",  "country": "Greece",      "country_flag": "🇬🇷", "league": "Super League",    "color": "#0D5EAF"},
]

# Default enabled leagues (top divisions only)
_DEFAULT_ENABLED = {"E0","D1","I1","SP1","F1","P1","T1","N1","B1","SC0","G1"}

_DEFAULT_CONFIG = {
    "version": "1.0",
    "plugins": {
        "corners": {"enabled": True,  "priority": 1, "name": "Угловые",         "emoji": "⛳", "color": "#00C896"},
        "cards":   {"enabled": True,  "priority": 2, "name": "Жёлтые Карточки", "emoji": "🟨", "color": "#FFD600"},
        "goals":   {"enabled": False, "priority": 3, "name": "Тотал Голов",     "emoji": "⚽", "color": "#4A9EFF"},
        "outcome": {"enabled": False, "priority": 4, "name": "Исход",           "emoji": "🏆", "color": "#FF6B6B"},
    },
    "bankroll": {
        "default": 50000, "conservative_percent": 0.02,
        "aggressive_percent": 0.05, "min_stake": 500, "max_stake_percent": 0.05,
    },
    "update": {
        # Replace OWNER/REPO with your actual GitHub private repo
        "version_url": "https://raw.githubusercontent.com/OWNER/REPO/main/version.json",
    },
}

_DEFAULT_SETTINGS = {lg["code"]: (lg["code"] in _DEFAULT_ENABLED) for lg in ALL_LEAGUES}


class Config:
    _data:     dict = {}
    _settings: dict = {}

    # ── Init ──────────────────────────────────────────────────────────────────

    @classmethod
    def load(cls):
        os.makedirs(DATA_DIR, exist_ok=True)
        # Load app config
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, encoding="utf-8") as f:
                    cls._data = {**_DEFAULT_CONFIG, **json.load(f)}
                logging.info("Config loaded from config.json")
            except Exception as e:
                logging.warning(f"Config load failed: {e}")
                cls._data = dict(_DEFAULT_CONFIG)
        else:
            cls._data = dict(_DEFAULT_CONFIG)
            cls._save_config()

        # Load settings (league on/off, user prefs)
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, encoding="utf-8") as f:
                    stored = json.load(f)
                    cls._settings = {**_DEFAULT_SETTINGS, **stored}
                logging.info("Settings loaded from data/settings.json")
            except Exception as e:
                logging.warning(f"Settings load failed: {e}")
                cls._settings = dict(_DEFAULT_SETTINGS)
        else:
            cls._settings = dict(_DEFAULT_SETTINGS)
            cls._save_settings()

    @classmethod
    def _save_config(cls):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cls._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Config save failed: {e}")

    @classmethod
    def _save_settings(cls):
        os.makedirs(DATA_DIR, exist_ok=True)
        try:
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(cls._settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Settings save failed: {e}")

    # ── League helpers ────────────────────────────────────────────────────────

    @classmethod
    def leagues(cls) -> list:
        """All leagues with enabled flag injected."""
        result = []
        for lg in ALL_LEAGUES:
            lg_copy = dict(lg)
            lg_copy["enabled"] = cls._settings.get(lg["code"], False)
            # Legacy compat: add 'name' and 'flag' aliases
            lg_copy["name"] = lg["country"]
            lg_copy["flag"] = lg["country_flag"]
            result.append(lg_copy)
        return result

    @classmethod
    def enabled_leagues(cls) -> list:
        return [lg for lg in cls.leagues() if lg["enabled"]]

    @classmethod
    def leagues_by_country(cls) -> dict:
        """Returns {country: [league_dict, ...]} ordered."""
        result: dict[str, list] = {}
        for lg in cls.leagues():
            c = lg["country"]
            result.setdefault(c, []).append(lg)
        return result

    @classmethod
    def set_league_enabled(cls, code: str, enabled: bool):
        cls._settings[code] = enabled
        cls._save_settings()

    @classmethod
    def league_by_code(cls, code: str) -> dict | None:
        for lg in cls.leagues():
            if lg["code"] == code:
                return lg
        return None

    # ── Plugin helpers ────────────────────────────────────────────────────────

    @classmethod
    def plugins(cls) -> dict:
        return cls._data.get("plugins", _DEFAULT_CONFIG["plugins"])

    # ── Generic get/set ───────────────────────────────────────────────────────

    @classmethod
    def get(cls, *keys, default=None):
        d = cls._data
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k, default)
            else:
                return default
        return d

    @classmethod
    def set(cls, value, *keys):
        d = cls._data
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = value
        cls._save_config()

    @classmethod
    def current_version(cls) -> str:
        from core.updater import get_local_version
        return get_local_version()

    @classmethod
    def version_check_url(cls) -> str:
        return cls._data.get("update", {}).get(
            "version_url",
            "https://raw.githubusercontent.com/footballai/predictor/main/version.json"
        )
