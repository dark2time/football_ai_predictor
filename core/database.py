"""
SQLite database for bets journal.
"""

import sqlite3
import os
import logging
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "betting_log.db")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "backups")


class Database:
    def __init__(self):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def _conn(self):
        return sqlite3.connect(DB_PATH)

    def initialize(self):
        with self._conn() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS bets (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    date        TEXT,
                    league      TEXT,
                    match       TEXT,
                    forecast    TEXT,
                    odds        REAL,
                    stake       INTEGER,
                    status      TEXT DEFAULT 'pending',
                    profit      INTEGER DEFAULT 0,
                    plugin      TEXT,
                    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.execute("""
                CREATE TABLE IF NOT EXISTS bankroll (
                    id      INTEGER PRIMARY KEY CHECK (id = 1),
                    amount  INTEGER DEFAULT 50000,
                    mode    TEXT    DEFAULT 'conservative'
                )
            """)
            con.execute("""
                INSERT OR IGNORE INTO bankroll (id, amount, mode) VALUES (1, 50000, 'conservative')
            """)
            con.commit()
        logging.info("Database initialized")
        self._maybe_backup()

    # ── Bankroll ──────────────────────────────────────────────────────────────

    def get_bankroll(self):
        with self._conn() as con:
            row = con.execute("SELECT amount, mode FROM bankroll WHERE id=1").fetchone()
            return {"amount": row[0], "mode": row[1]} if row else {"amount": 50000, "mode": "conservative"}

    def set_bankroll(self, amount: int):
        with self._conn() as con:
            con.execute("UPDATE bankroll SET amount=? WHERE id=1", (amount,))
            con.commit()

    def set_mode(self, mode: str):
        with self._conn() as con:
            con.execute("UPDATE bankroll SET mode=? WHERE id=1", (mode,))
            con.commit()

    def adjust_bankroll(self, delta: int):
        with self._conn() as con:
            con.execute("UPDATE bankroll SET amount = amount + ? WHERE id=1", (delta,))
            con.commit()

    # ── Bets ──────────────────────────────────────────────────────────────────

    def place_bet(self, date, league, match, forecast, odds, stake, plugin="corners"):
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO bets (date,league,match,forecast,odds,stake,status,profit,plugin) "
                "VALUES (?,?,?,?,?,?,'pending',0,?)",
                (date, league, match, forecast, odds, stake, plugin),
            )
            con.commit()
            self.adjust_bankroll(-stake)
            logging.info(f"Bet placed: {match} | {forecast} | stake={stake}")
            return cur.lastrowid

    def get_all_bets(self, league=None, status=None):
        sql = "SELECT * FROM bets"
        params = []
        clauses = []
        if league:
            clauses.append("league=?"); params.append(league)
        if status:
            clauses.append("status=?"); params.append(status)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC"
        with self._conn() as con:
            rows = con.execute(sql, params).fetchall()
        cols = ["id","date","league","match","forecast","odds","stake","status","profit","plugin","created_at"]
        return [dict(zip(cols, r)) for r in rows]

    def get_pending_bets(self):
        return self.get_all_bets(status="pending")

    def update_bet_result(self, bet_id: int, result: str):
        bet_list = self.get_all_bets()
        bet = next((b for b in bet_list if b["id"] == bet_id), None)
        if not bet:
            return
        if result == "won":
            returns = int(bet["stake"] * bet["odds"])
            profit  = returns - bet["stake"]
            self.adjust_bankroll(returns)
        else:
            profit = -bet["stake"]
        with self._conn() as con:
            con.execute(
                "UPDATE bets SET status=?, profit=? WHERE id=?",
                (result, profit, bet_id),
            )
            con.commit()
        logging.info(f"Bet {bet_id} updated to {result}, profit={profit}")

    def manual_update_status(self, bet_id: int, new_status: str):
        """Allow user to manually override a bet status."""
        bets = self.get_all_bets()
        bet  = next((b for b in bets if b["id"] == bet_id), None)
        if not bet:
            return
        old_status = bet["status"]
        if old_status == new_status:
            return
        # Reverse old effect
        if old_status == "won":
            self.adjust_bankroll(-(bet["stake"] + bet["profit"]))
        elif old_status == "pending" and new_status != "pending":
            pass  # stake already deducted when placed
        # Apply new effect
        if new_status == "won":
            returns = int(bet["stake"] * bet["odds"])
            profit  = returns - bet["stake"]
            self.adjust_bankroll(returns)
        else:
            profit = -bet["stake"]
        with self._conn() as con:
            con.execute("UPDATE bets SET status=?, profit=? WHERE id=?", (new_status, profit, bet_id))
            con.commit()

    def get_stats(self):
        bets = self.get_all_bets()
        settled = [b for b in bets if b["status"] != "pending"]
        won     = [b for b in settled if b["status"] == "won"]
        total_staked = sum(b["stake"] for b in settled)
        total_profit = sum(b["profit"] for b in bets)
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
        winrate = (len(won) / len(settled) * 100) if settled else 0

        # Per-league
        leagues = {}
        for b in settled:
            lg = b["league"]
            if lg not in leagues:
                leagues[lg] = {"staked": 0, "profit": 0, "won": 0, "total": 0}
            leagues[lg]["staked"] += b["stake"]
            leagues[lg]["profit"] += b["profit"]
            leagues[lg]["total"]  += 1
            if b["status"] == "won":
                leagues[lg]["won"] += 1
        for lg in leagues:
            s = leagues[lg]
            s["roi"]     = (s["profit"] / s["staked"] * 100) if s["staked"] > 0 else 0
            s["winrate"] = (s["won"] / s["total"] * 100) if s["total"] > 0 else 0

        return {
            "total":        len(bets),
            "settled":      len(settled),
            "won":          len(won),
            "winrate":      winrate,
            "roi":          roi,
            "total_profit": total_profit,
            "by_league":    leagues,
        }

    # ── Backup ────────────────────────────────────────────────────────────────

    def _maybe_backup(self):
        stamp = datetime.now().strftime("%Y%m%d")
        backup_path = os.path.join(BACKUP_DIR, f"betting_log_{stamp}.db")
        if not os.path.exists(backup_path) and os.path.exists(DB_PATH):
            try:
                shutil.copy2(DB_PATH, backup_path)
                logging.info(f"DB backup created: {backup_path}")
            except Exception as e:
                logging.warning(f"Backup failed: {e}")
