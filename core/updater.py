"""
Updater v1.0 — GitHub Releases
────────────────────────────────────────────────────────────
Flow:
  1. GET version.json from GitHub raw URL
  2. Compare with local version.json
  3. If newer → offer download
  4. Download update.zip from GitHub Releases
  5. Extract, replace app files (data/ is NEVER touched)
  6. Restart

Remote version.json format:
  {
    "version": "1.1",
    "download_url": "https://github.com/OWNER/REPO/releases/download/1.1/update.zip"
  }
────────────────────────────────────────────────────────────
"""

import os
import json
import logging
import zipfile
import shutil
import sys
import requests

APP_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(APP_DIR, "version.json")
TMP_ZIP      = os.path.join(APP_DIR, "_update_download.zip")
TMP_DIR      = os.path.join(APP_DIR, "_update_tmp")

# ── Folders that must NEVER be touched during update ──────────────────────────
PROTECTED_DIRS = {"data", "database", "logs"}


def get_local_version() -> str:
    """Read version from local version.json. Returns '0.0' if missing."""
    if os.path.exists(VERSION_FILE):
        try:
            with open(VERSION_FILE, encoding="utf-8") as f:
                return json.load(f).get("version", "0.0")
        except Exception:
            pass
    return "0.0"


def check_for_update(version_url: str) -> dict | None:
    """
    Fetch remote version.json and compare with local.
    Returns remote info dict if update available, else None.
    """
    local = get_local_version()
    try:
        resp = requests.get(version_url, timeout=10,
                            headers={"Cache-Control": "no-cache"})
        resp.raise_for_status()
        remote = resp.json()
        remote_ver = remote.get("version", "0.0")

        if _version_gt(remote_ver, local):
            logging.info(f"Update available: {local} → {remote_ver}")
            return remote
        else:
            logging.info(f"Up to date (v{local})")
            return None
    except requests.exceptions.ConnectionError:
        logging.warning("Update check: no internet connection")
    except Exception as e:
        logging.warning(f"Update check failed: {e}")
    return None


def download_and_install(update_info: dict, progress_cb=None) -> bool:
    """
    Download update.zip from GitHub Releases and install.
    data/ folder is NEVER modified.
    Returns True on success.
    """
    url = update_info.get("download_url")
    if not url:
        logging.error("No download_url in update info")
        return False

    try:
        # 1. Download
        _progress(progress_cb, 5, "Скачиваю обновление с GitHub…")
        resp = requests.get(url, timeout=120, stream=True,
                            headers={"User-Agent": "FootballAI-Updater/1.0"})
        resp.raise_for_status()

        total      = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(TMP_ZIP, "wb") as f:
            for chunk in resp.iter_content(chunk_size=32768):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_cb:
                        pct = 5 + int(downloaded / total * 55)
                        progress_cb(pct, f"Скачано {downloaded // 1024} / {total // 1024} KB…")

        _progress(progress_cb, 62, "Проверяю архив…")
        if not zipfile.is_zipfile(TMP_ZIP):
            logging.error("Downloaded file is not a valid ZIP")
            _cleanup()
            return False

        # 2. Extract to temp dir
        _progress(progress_cb, 65, "Распаковываю…")
        if os.path.exists(TMP_DIR):
            shutil.rmtree(TMP_DIR)
        with zipfile.ZipFile(TMP_ZIP, "r") as zf:
            zf.extractall(TMP_DIR)

        # 3. Copy files (skip protected dirs)
        _progress(progress_cb, 78, "Устанавливаю файлы…")
        _copy_update(TMP_DIR, APP_DIR)

        # 4. Update local version.json
        new_ver = update_info.get("version", "0.0")
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            json.dump({"version": new_ver}, f, indent=2)

        _progress(progress_cb, 100, f"Обновление до v{new_ver} установлено!")
        logging.info(f"Update to v{new_ver} installed successfully")
        _cleanup()
        return True

    except requests.exceptions.ConnectionError:
        logging.error("Update download: no internet connection")
    except Exception as e:
        logging.error(f"Update install error: {e}")

    _cleanup()
    return False


def restart_app():
    """Replace current process with a fresh Python process."""
    try:
        logging.info("Restarting application…")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logging.error(f"Restart failed: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _version_gt(a: str, b: str) -> bool:
    """Return True if version a > version b (e.g. '1.1' > '1.0')."""
    def parts(v):
        try:
            return tuple(int(x) for x in str(v).split("."))
        except Exception:
            return (0,)
    return parts(a) > parts(b)


def _copy_update(src_dir: str, dst_dir: str):
    """
    Recursively copy src_dir → dst_dir.
    Protected dirs in dst (data/, database/, logs/) are completely skipped.
    """
    protected_abs = {
        os.path.normpath(os.path.join(dst_dir, d)) for d in PROTECTED_DIRS
    }

    for root, dirs, files in os.walk(src_dir, topdown=True):
        rel  = os.path.relpath(root, src_dir)
        dst  = os.path.normpath(os.path.join(dst_dir, rel))

        # Skip if destination is a protected folder
        if any(dst == p or dst.startswith(p + os.sep) for p in protected_abs):
            dirs.clear()
            continue

        os.makedirs(dst, exist_ok=True)

        for fname in files:
            src_f = os.path.join(root, fname)
            dst_f = os.path.join(dst, fname)
            try:
                shutil.copy2(src_f, dst_f)
                logging.debug(f"  updated: {os.path.relpath(dst_f, dst_dir)}")
            except Exception as e:
                logging.warning(f"  could not copy {fname}: {e}")


def _progress(cb, pct: int, msg: str):
    if cb:
        cb(pct, msg)


def _cleanup():
    for path in [TMP_ZIP, TMP_DIR]:
        try:
            if os.path.isfile(path):  os.remove(path)
            if os.path.isdir(path):   shutil.rmtree(path)
        except Exception:
            pass
