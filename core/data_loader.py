"""
Data loader v3.1 — incremental updates, robust date parsing, CSV error tolerance.
"""

import os
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import StringIO

DATA_DIR    = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "csv")
LEAGUES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "leagues")
BASE_URL    = "https://www.football-data.co.uk/mmz4281/{season}/{league}.csv"
FIXTURE_URL = "https://www.football-data.co.uk/fixtures.csv"


def _season_code(year: int) -> str:
    return f"{str(year)[2:]}{str(year+1)[2:]}"


def _all_seasons() -> list:
    today = datetime.now()
    return [_season_code(y) for y in range(2005, today.year + 1)]


class DataLoader:

    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    def load_league(self, league_code: str, progress_cb=None, force_full: bool = False) -> pd.DataFrame:
        seasons = _all_seasons()
        frames  = []
        total   = len(seasons)

        for i, season in enumerate(seasons):
            if progress_cb:
                pct = 5 + int(i / total * 50)
                progress_cb(pct, f"Загрузка сезона {season}…")

            cache = os.path.join(DATA_DIR, f"{league_code}_{season}.csv")
            df    = self._get_season(league_code, season, cache, force_full)
            if df is not None and not df.empty:
                frames.append(df)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)
        combined = self._clean(combined)

        # BUG FIX: ensure Date is datetime before comparison
        if "Date" in combined.columns:
            combined["Date"] = pd.to_datetime(combined["Date"], errors="coerce")
            combined = combined.dropna(subset=["Date"])

        cutoff = pd.Timestamp(datetime.now() - timedelta(days=1))
        combined = combined[combined["Date"] <= cutoff].copy()

        logging.info(f"{league_code}: {len(combined)} historical matches loaded")
        return combined.sort_values("Date").reset_index(drop=True)

    def load_fixtures(self, league_code: str) -> pd.DataFrame:
        today = pd.Timestamp(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
        end   = pd.Timestamp(datetime.now() + timedelta(days=21))
        cache = os.path.join(DATA_DIR, "fixtures.csv")
        df    = self._fetch_url(FIXTURE_URL, cache, max_age_hours=6)

        if df is None or df.empty:
            return pd.DataFrame()

        df = self._clean(df)
        if df.empty:
            return pd.DataFrame()

        # Ensure datetime
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])

        if "Div" in df.columns:
            df = df[df["Div"] == league_code].copy()

        df = df[(df["Date"] >= today) & (df["Date"] <= end)].copy()
        logging.info(f"Fixtures for {league_code}: {len(df)} matches")
        return df.sort_values("Date").reset_index(drop=True)

    def load_all_fixtures(self) -> pd.DataFrame:
        today = pd.Timestamp(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))
        end   = pd.Timestamp(datetime.now() + timedelta(days=21))
        cache = os.path.join(DATA_DIR, "fixtures.csv")
        df    = self._fetch_url(FIXTURE_URL, cache, max_age_hours=6)

        if df is None or df.empty:
            return pd.DataFrame()

        df = self._clean(df)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        df = df[(df["Date"] >= today) & (df["Date"] <= end)].copy()
        return df.sort_values("Date").reset_index(drop=True)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_season(self, league, season, cache_path, force_full):
        today      = datetime.now()
        cur_season = _season_code(today.year if today.month >= 7 else today.year - 1)
        is_current = (season == cur_season)

        if os.path.exists(cache_path) and not force_full:
            if not is_current:
                try:
                    df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
                    if not df.empty:
                        return df
                except Exception:
                    pass
            else:
                age_h = (today.timestamp() - os.path.getmtime(cache_path)) / 3600
                if age_h < 6:
                    try:
                        df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
                        if not df.empty:
                            return df
                    except Exception:
                        pass

        url = BASE_URL.format(season=season, league=league)
        return self._fetch_url(url, cache_path)

    def _fetch_url(self, url, cache_path, max_age_hours=24):
        if os.path.exists(cache_path):
            age_h = (datetime.now().timestamp() - os.path.getmtime(cache_path)) / 3600
            if age_h < max_age_hours:
                try:
                    df = pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
                    if not df.empty:
                        return df
                except Exception:
                    pass

        try:
            resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            text = resp.content.decode("latin-1")
            # error_bad_lines removed in newer pandas — use on_bad_lines
            try:
                df = pd.read_csv(StringIO(text), low_memory=False, on_bad_lines="skip")
            except TypeError:
                df = pd.read_csv(StringIO(text), low_memory=False, error_bad_lines=False)

            if df.empty:
                return None
            df.to_csv(cache_path, index=False, encoding="utf-8")
            logging.info(f"Downloaded: {url}")
            return df

        except requests.exceptions.ConnectionError:
            if os.path.exists(cache_path):
                try:
                    return pd.read_csv(cache_path, encoding="utf-8", low_memory=False)
                except Exception:
                    pass
        except requests.exceptions.HTTPError as e:
            if hasattr(e, "response") and e.response and e.response.status_code == 404:
                pass
            else:
                logging.warning(f"HTTP error {url}: {e}")
        except Exception as e:
            logging.warning(f"Error loading {url}: {e}")
        return None

    @staticmethod
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        # Drop completely empty rows
        df = df.dropna(how="all").copy()

        if "HomeTeam" in df.columns:
            df = df.dropna(subset=["HomeTeam"]).copy()

        if "Date" in df.columns:
            # Try multiple formats, then fallback to dateutil
            parsed = None
            for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]:
                try:
                    parsed = pd.to_datetime(df["Date"], format=fmt)
                    break
                except Exception:
                    continue
            if parsed is None:
                try:
                    parsed = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
                except Exception:
                    parsed = pd.to_datetime(df["Date"], errors="coerce")
            df["Date"] = parsed
            df = df.dropna(subset=["Date"]).copy()

        for col in ["FTHG","FTAG","HC","AC","HY","AY","B365H","B365D","B365A"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
