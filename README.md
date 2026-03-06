# Football AI Predictor Pro — v1.0

A desktop application for finding **value bets** in football using machine learning.  
Focus markets: **Corners** and **Yellow Cards** — where bookmakers make the most statistical errors.

---

## Table of Contents

1. [Project Description](#project-description)
2. [Installation](#installation)
3. [Project Structure](#project-structure)
4. [How to Run](#how-to-run)
5. [How the Update System Works](#how-the-update-system-works)
6. [Releasing New Versions (Developer Guide)](#releasing-new-versions)
7. [GitHub Repository Setup](#github-repository-setup)

---

## Project Description

Football AI Predictor Pro analyses historical match data from **football-data.co.uk** (from 2005 to today), trains machine learning models, and identifies upcoming fixtures where the model's probability exceeds the bookmaker's implied probability by at least 8%.

### Supported Leagues (18 total)

| Country      | League Code | League Name      |
|--------------|-------------|------------------|
| England      | E0          | Premier League   |
| England      | E1          | Championship     |
| England      | E2          | League One       |
| England      | E3          | League Two       |
| Scotland     | SC0         | Premiership      |
| Scotland     | SC1         | Championship     |
| Germany      | D1          | Bundesliga       |
| Germany      | D2          | Bundesliga 2     |
| Italy        | I1          | Serie A          |
| Italy        | I2          | Serie B          |
| Spain        | SP1         | La Liga          |
| Spain        | SP2         | Segunda          |
| France       | F1          | Ligue 1          |
| France       | F2          | Ligue 2          |
| Netherlands  | N1          | Eredivisie       |
| Belgium      | B1          | Pro League       |
| Portugal     | P1          | Primeira Liga    |
| Turkey       | T1          | Süper Lig        |
| Greece       | G1          | Super League     |

### Key Features

- **Value bet filter**: only shows bets where `probability × odds ≥ 1.08`
- **Incremental backtest**: 90-day evaluation window, model trained once (not per match)
- **Top Matches Today**: best bets from all leagues on one screen
- **League ON/OFF toggles**: disable leagues you don't want to bet on
- **Auto update**: one-click update from GitHub Releases, user data never deleted

---

## Installation

### Requirements

- Python 3.10 or newer
- Windows, macOS, or Linux

### Step 1 — Install dependencies

**Windows (double-click):**
```
install.bat
```

**Manual (any OS):**
```bash
pip install PyQt6 pandas numpy scikit-learn scipy requests joblib
```

### Step 2 — Run the application

```bash
python main.py
```

---

## Project Structure

```
football_ai_predictor/
│
├── main.py                    # Entry point
├── version.json               # Current app version (e.g. {"version": "1.0"})
├── config.json                # App configuration (auto-generated)
├── requirements.txt
├── install.bat                # Windows installer
├── README.md
│
├── core/                      # Business logic (do not modify)
│   ├── config.py              # League list, settings loader
│   ├── data_loader.py         # CSV download & caching
│   ├── feature_engineering.py # ML features + time weights
│   ├── backtesting.py         # 90-day backtest engine
│   ├── model_store.py         # Model save/load (joblib)
│   ├── database.py            # SQLite bankroll & bet log
│   ├── auto_checker.py        # Auto-checks pending bets vs results
│   ├── value_filter.py        # probability >= 0.55, value >= 1.08
│   └── updater.py             # GitHub update system ← this file
│
├── plugins/                   # Prediction models (one per market)
│   ├── corners_plugin.py      # GradientBoosting for corners
│   ├── cards_plugin.py        # RandomForest for cards
│   ├── goals_plugin.py        # Goals total
│   └── outcome_plugin.py      # Match result P1/X/P2
│
├── gui/                       # PyQt6 interface
│   ├── main_window.py
│   ├── league_selector.py     # Main screen: leagues by country
│   ├── dashboard.py           # Fixtures + history for one league
│   ├── match_analysis.py      # Prediction modal
│   ├── betting_log.py         # Full bet history
│   ├── settings_dialog.py     # Bankroll & plugin settings
│   ├── update_dialog.py       # Update check UI
│   └── styles.py              # Design system (dark theme)
│
├── parsers/
│   └── oddsportal_parser.py   # Odds scraper (optional)
│
└── data/                      # USER DATA — never deleted on update
    ├── settings.json          # League ON/OFF, user preferences
    ├── csv/                   # Cached historical CSV files
    ├── leagues/               # Per-league data files
    ├── models/                # Trained ML models (.pkl)
    ├── backtest/              # Incremental backtest results (.json)
    ├── fixtures/              # Upcoming matches
    └── league_stats.json      # ROI/Winrate per league per market
```

> **Important:** The `data/` folder is **never modified** during updates.  
> All user data (CSV, models, statistics, settings) is preserved.

---

## How to Run

```bash
python main.py
```

On first launch:
1. Accept the disclaimer
2. Click **"Загрузить все лиги"** — this downloads historical data and trains models
3. View **Top Matches Today** for best value bets
4. Click on any league to open its dashboard
5. Click **"Анализ"** on a fixture to see the full prediction

---

## How the Update System Works

### User flow

1. Click **"Проверить обновления"** in the app
2. The app fetches `version.json` from GitHub
3. If a newer version is found, a notification appears
4. Click **"Установить обновление"**
5. `update.zip` is downloaded from GitHub Releases
6. Files are extracted and replaced in the app folder
7. The `data/` folder is **never touched**
8. The app restarts automatically

### Protected folders (never modified during update)

```
data/
database/
logs/
```

### Remote version.json format

Hosted at:
```
https://raw.githubusercontent.com/OWNER/REPO/main/version.json
```

Format:
```json
{
  "version": "1.1",
  "download_url": "https://github.com/OWNER/REPO/releases/download/1.1/update.zip"
}
```

---

## Releasing New Versions

Follow these steps every time you release a new version:

### Step 1 — Make your code changes

Edit files in the project. Do **not** include anything from `data/` in the release.

### Step 2 — Update version.json

Edit `version.json` in the repo root:
```json
{
  "version": "1.1"
}
```

### Step 3 — Build update.zip

The archive should contain **only app code** — no `data/`, no `.db`, no logs.

```bash
# Windows PowerShell
Compress-Archive -Path main.py,core,gui,plugins,parsers,requirements.txt,version.json,install.bat -DestinationPath update.zip
```

```bash
# Linux / macOS
zip -r update.zip main.py core/ gui/ plugins/ parsers/ requirements.txt version.json install.bat README.md \
    --exclude "*.pyc" --exclude "*/__pycache__/*"
```

### Step 4 — Create a GitHub Release

1. Go to your repository on GitHub
2. Click **Releases** → **Draft a new release**
3. Set tag: `1.1`
4. Set title: `v1.1`
5. Upload `update.zip` as a release asset
6. Publish the release

### Step 5 — Update version.json in the repo

Edit `version.json` in the repository root to point to the new release:
```json
{
  "version": "1.1",
  "download_url": "https://github.com/OWNER/REPO/releases/download/1.1/update.zip"
}
```

Commit and push. The app will now detect the new version on next check.

---

## GitHub Repository Setup

### Creating a private repository

1. Go to [github.com](https://github.com) and sign in
2. Click **New repository**
3. Set **Repository name**: `football-ai-predictor` (or any name)
4. Set visibility to **Private** ← important, keeps your code private
5. Click **Create repository**

### Uploading the project

```bash
git init
git add .
git commit -m "Initial release v1.0"
git branch -M main
git remote add origin https://github.com/OWNER/REPO.git
git push -u origin main
```

### Configuring the update URL in the app

Edit `config.json` in the app folder (auto-generated on first run):
```json
{
  "update": {
    "version_url": "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/version.json"
  }
}
```

Replace `YOUR_USERNAME` and `YOUR_REPO` with your actual GitHub username and repository name.

### Setting up GitHub Releases

1. After pushing code, go to **Releases** on your repo page
2. Click **Draft a new release**
3. Create a tag `1.0`
4. Upload `update.zip`
5. Publish

Every subsequent release follows the same pattern with an incremented version number.

---

## Disclaimer

This software is provided for statistical analysis purposes only.  
Sports betting involves financial risk. Past model performance does not guarantee future results.  
Use only funds you can afford to lose. Ensure betting is legal in your jurisdiction.
