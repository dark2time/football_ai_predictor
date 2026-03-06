"""
OddsPortal coefficient parser using Selenium (headless).
Falls back gracefully if Selenium/Chrome not available.
"""

import logging
import time
import json
import os
import hashlib
from datetime import datetime, timedelta

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache")
CACHE_TTL_MINUTES = 30


def _cache_key(home, away, date_str):
    raw = f"{home}|{away}|{date_str}".lower().replace(" ", "_")
    return hashlib.md5(raw.encode()).hexdigest()


def _cache_path(key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"odds_{key}.json")


def _load_cache(key):
    path = _cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            data = json.load(f)
        cached_time = datetime.fromisoformat(data["cached_at"])
        if datetime.now() - cached_time < timedelta(minutes=CACHE_TTL_MINUTES):
            return data["odds"]
    except Exception:
        pass
    return None


def _save_cache(key, odds):
    path = _cache_path(key)
    try:
        with open(path, "w") as f:
            json.dump({"cached_at": datetime.now().isoformat(), "odds": odds}, f)
    except Exception:
        pass


def fetch_odds(home: str, away: str, match_date: str) -> dict | None:
    """
    Attempt to scrape live odds from OddsPortal.
    Returns dict like:
        {
            "corners_over": {"line": 9.5, "odds": 1.90},
            "cards_over":   {"line": 4.5, "odds": 2.00},
            "goals_over":   {"line": 2.5, "odds": 1.85},
        }
    or None if unavailable.
    """
    key = _cache_key(home, away, match_date)
    cached = _load_cache(key)
    if cached:
        return cached

    try:
        result = _scrape_oddsportal(home, away, match_date)
    except Exception as e:
        logging.warning(f"OddsPortal scraping failed ({home} vs {away}): {e}")
        result = None

    if result:
        _save_cache(key, result)
    return result


def _scrape_oddsportal(home, away, match_date):
    """
    Attempt headless Selenium scrape.
    If Selenium/Chrome not available, raises ImportError/WebDriverException.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError as e:
        raise ImportError(f"Selenium/ChromeDriver not available: {e}")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=options)

        query   = f"{home} {away}".replace(" ", "+")
        url     = f"https://www.oddsportal.com/search/#!{query}"
        driver.get(url)
        time.sleep(3)

        # Very simplified — real implementation would navigate to match page
        # and extract specific odds tables. This scaffold shows the pattern.
        logging.info(f"OddsPortal: searching for {home} vs {away}")
        # TODO: implement full scraping logic per OddsPortal DOM structure
        return None

    finally:
        if driver:
            driver.quit()
