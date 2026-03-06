"""
League Selector v1.0
─────────────────────────────────────────────────────────────
• 18 leagues grouped by country
• Per-league ON/OFF toggle — saved to data/settings.json
• Best market per league (highest ROI from league_stats.json)
• Top Matches Today block
• "Обновить данные" and "Проверить обновления" buttons
─────────────────────────────────────────────────────────────
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt

from core.config import Config
from core.database import Database
from core.backtesting import Backtester
from gui.styles import S
from gui.widgets import StatCard, SectionLabel, h_sep


class LeagueSelectorScreen(QWidget):
    league_selected     = pyqtSignal(dict)
    load_all_requested  = pyqtSignal()
    refresh_requested   = pyqtSignal()   # "Обновить данные"

    def __init__(self, db: Database):
        super().__init__()
        self.db       = db
        self._payloads = {}
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(S.scroll_area())
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(44, 32, 44, 32)
        root.setSpacing(0)
        scroll.setWidget(content)
        outer.addWidget(scroll)

        # ── Header ────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        tcol = QVBoxLayout(); tcol.setSpacing(4)
        sub = QLabel("FOOTBALL AI")
        sub.setStyleSheet(f"color:{S.success};font-size:10px;letter-spacing:4px;font-weight:700;")
        tcol.addWidget(sub)
        title = QLabel("Predictor Pro")
        title.setStyleSheet("color:#E2E8F0;font-size:30px;font-weight:700;")
        tcol.addWidget(title)
        ver = QLabel("v1.0 — Value Betting System")
        ver.setStyleSheet(f"color:{S.dim};font-size:11px;")
        tcol.addWidget(ver)
        hdr.addLayout(tcol)
        hdr.addStretch()

        # Global stats
        self._g_bank = StatCard("Банк",    "—")
        self._g_roi  = StatCard("ROI",     "—",  S.success)
        self._g_wr   = StatCard("Winrate", "—",  S.info)
        self._g_bets = StatCard("Ставок",  "0")
        for c in [self._g_bank, self._g_roi, self._g_wr, self._g_bets]:
            c.setFixedWidth(118)
            hdr.addWidget(c)
        root.addLayout(hdr)
        root.addSpacing(22)
        root.addWidget(h_sep())
        root.addSpacing(22)

        # ── Action buttons ────────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)

        load_btn = QPushButton("⚡  Загрузить все лиги")
        load_btn.setFixedHeight(44)
        load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        load_btn.setStyleSheet(S.btn_solid())
        load_btn.setToolTip("Загружает данные, обучает модели, анализирует все включённые лиги")
        load_btn.clicked.connect(self.load_all_requested.emit)
        btn_row.addWidget(load_btn, 3)

        refresh_btn = QPushButton("🔄  Обновить данные")
        refresh_btn.setFixedHeight(44)
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.setStyleSheet(S.btn_primary(S.info))
        refresh_btn.setToolTip("Скачивает свежие CSV, добавляет только новые матчи")
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        btn_row.addWidget(refresh_btn, 2)

        update_btn = QPushButton("⬆  Проверить обновления")
        update_btn.setFixedHeight(44)
        update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        update_btn.setStyleSheet(S.btn_ghost())
        update_btn.clicked.connect(self._open_update_dialog)
        btn_row.addWidget(update_btn, 2)

        root.addLayout(btn_row)
        root.addSpacing(28)

        # ── Top Matches Today ─────────────────────────────────────────────────
        root.addWidget(SectionLabel("🏆  TOP MATCHES TODAY"))
        root.addSpacing(10)

        self._tm_frame = QFrame()
        self._tm_frame.setStyleSheet(S.card())
        tm_l = QVBoxLayout(self._tm_frame)
        tm_l.setContentsMargins(16,14,16,14); tm_l.setSpacing(0)

        self._tm_header = self._make_top_header()
        tm_l.addWidget(self._tm_header); self._tm_header.hide()

        self._tm_placeholder = QLabel(
            "Нажмите «Загрузить все лиги», чтобы увидеть лучшие матчи дня."
        )
        self._tm_placeholder.setStyleSheet(f"color:{S.muted};font-size:12px;padding:6px 0;")
        tm_l.addWidget(self._tm_placeholder)

        self._tm_rows = QVBoxLayout(); self._tm_rows.setSpacing(1)
        tm_l.addLayout(self._tm_rows)
        root.addWidget(self._tm_frame)
        root.addSpacing(32)

        # ── League grid (grouped by country) ─────────────────────────────────
        root.addWidget(SectionLabel("Лиги по странам"))
        root.addSpacing(14)
        self._leagues_container = QVBoxLayout()
        self._leagues_container.setSpacing(24)
        root.addLayout(self._leagues_container)
        root.addStretch()

        self._rebuild_leagues()
        self._refresh_global_stats()

    # ── Top Matches Today ─────────────────────────────────────────────────────

    def _make_top_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"border-bottom:1px solid {S.border2};")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(6,4,6,8); layout.setSpacing(0)
        for lbl, s in [("МАТЧ",12),("РЫНОК",9),("ВЕРОЯТНОСТЬ",6),
                        ("КОЭФ",4),("VALUE",5),("ЛИГА",8),("ДАТА",5)]:
            l = QLabel(lbl)
            l.setStyleSheet(f"color:{S.dim};font-size:9px;letter-spacing:1.5px;font-weight:700;")
            layout.addWidget(l, s)
        return w

    def set_top_value(self, bets: list):
        while self._tm_rows.count():
            item = self._tm_rows.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not bets:
            self._tm_placeholder.setText("Нет подходящих ставок на ближайшие матчи.")
            self._tm_placeholder.show(); self._tm_header.hide()
            return
        self._tm_placeholder.hide(); self._tm_header.show()
        for i, bet in enumerate(bets):
            self._tm_rows.addWidget(self._make_top_row(bet, i % 2 == 0))

    def _make_top_row(self, bet: dict, alt: bool) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{'#0B0F1A' if alt else '#111827'};border-radius:4px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(6,10,6,10); layout.setSpacing(0)
        prob  = bet.get("probability", 0)
        vpct  = bet.get("value_pct",   0)
        odds  = bet.get("odds",        0)
        value = prob * odds

        def cell(text, color="#D1D5DB", bold=False, s=1):
            l = QLabel(text)
            l.setStyleSheet(f"color:{color};font-size:12px;font-weight:{'700' if bold else '400'};")
            layout.addWidget(l, s)

        cell(bet.get("match",""),    "#E2E8F0", bold=True, s=12)
        cell(bet.get("market",""),   S.muted,   s=9)
        cell(f"{prob:.0%}",         S.success, bold=True, s=6)
        cell(f"{odds:.2f}",         S.info,    s=4)
        cell(f"{value:.2f}",        S.warning, bold=True, s=5)
        cell(bet.get("league",""),  S.dim,     s=8)
        cell(bet.get("date",""),    S.dim,     s=5)
        return w

    # ── League grid by country ────────────────────────────────────────────────

    def _rebuild_leagues(self):
        # Clear existing
        while self._leagues_container.count():
            item = self._leagues_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        lg_stats = Backtester.load_league_stats()
        db_stats = self.db.get_stats()

        for country, leagues in Config.leagues_by_country().items():
            block = self._make_country_block(country, leagues, lg_stats, db_stats)
            self._leagues_container.addWidget(block)

    def _make_country_block(self, country: str, leagues: list,
                             lg_stats: dict, db_stats: dict) -> QFrame:
        block = QFrame()
        block.setStyleSheet(f"background:#111827;border:1px solid #1F2937;border-radius:10px;")
        layout = QVBoxLayout(block)
        layout.setContentsMargins(18,16,18,16); layout.setSpacing(10)

        # Country header
        hdr = QHBoxLayout()
        flag = leagues[0].get("country_flag","")
        hdr.addWidget(QLabel(flag, styleSheet="font-size:22px;"))
        hdr.addWidget(QLabel(country,
            styleSheet="color:#E2E8F0;font-size:15px;font-weight:700;margin-left:8px;"))
        hdr.addStretch()
        # Summary: how many enabled
        enabled_count = sum(1 for lg in leagues if lg.get("enabled"))
        hdr.addWidget(QLabel(f"{enabled_count}/{len(leagues)} вкл.",
            styleSheet=f"color:{S.dim};font-size:10px;"))
        layout.addLayout(hdr)

        # Divider
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{S.border};")
        layout.addWidget(sep)

        # League rows
        for lg in leagues:
            row = self._make_league_row(lg, lg_stats.get(lg["code"],{}),
                                        db_stats["by_league"].get(lg["code"],{}))
            layout.addWidget(row)
        return block

    def _make_league_row(self, lg: dict, bt: dict, db: dict) -> QWidget:
        code    = lg["code"]
        enabled = lg.get("enabled", False)
        ready   = code in self._payloads

        # Best market = highest ROI among corners/cards/goals
        best_market, best_roi = self._best_market(bt)

        row = QFrame()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(f"""
            QFrame {{ background:{'#0B0F1A' if enabled else '#0d1118'};
                      border:1px solid {'#2a3545' if enabled else '#1a2030'};
                      border-radius:8px; }}
            QFrame:hover {{ background:#1a2535; border-color:{S.success}; }}
        """)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(14,12,14,12); row_layout.setSpacing(14)

        # League name
        name_col = QVBoxLayout(); name_col.setSpacing(2)
        name_col.addWidget(QLabel(lg["league"],
            styleSheet=f"color:{'#E2E8F0' if enabled else '#6B7280'};font-size:13px;font-weight:700;"))
        name_col.addWidget(QLabel(code,
            styleSheet=f"color:{S.dim};font-size:10px;letter-spacing:1px;"))
        row_layout.addLayout(name_col, 4)

        # Best market badge
        if best_market:
            m_emoji = {"corners":"⛳","cards":"🟨","goals":"⚽"}.get(best_market,"📊")
            m_label = {"corners":"Угловые","cards":"ЖК","goals":"Голы"}.get(best_market,best_market)
            bm_col = QVBoxLayout(); bm_col.setSpacing(2)
            bm_col.addWidget(QLabel("BEST MARKET",
                styleSheet=f"color:{S.dim};font-size:9px;letter-spacing:1px;font-weight:600;"))
            bm_col.addWidget(QLabel(f"{m_emoji} {m_label}",
                styleSheet=f"color:{S.success};font-size:12px;font-weight:700;"))
            row_layout.addLayout(bm_col, 3)

        # ROI
        roi_col = QVBoxLayout(); roi_col.setSpacing(2)
        roi_col.addWidget(QLabel("ROI",
            styleSheet=f"color:{S.dim};font-size:9px;letter-spacing:1px;font-weight:600;"))
        roi_color = S.success if best_roi >= 0 else S.error
        roi_col.addWidget(QLabel(f"{'+' if best_roi>=0 else ''}{best_roi:.0f}%",
            styleSheet=f"color:{roi_color};font-size:13px;font-weight:700;"))
        row_layout.addLayout(roi_col, 2)

        # Winrate
        best_wr = self._best_winrate(bt)
        wr_col = QVBoxLayout(); wr_col.setSpacing(2)
        wr_col.addWidget(QLabel("WINRATE",
            styleSheet=f"color:{S.dim};font-size:9px;letter-spacing:1px;font-weight:600;"))
        wr_col.addWidget(QLabel(f"{best_wr:.0f}%",
            styleSheet=f"color:{S.info};font-size:13px;font-weight:700;"))
        row_layout.addLayout(wr_col, 2)

        row_layout.addStretch()

        # Ready badge
        if ready:
            row_layout.addWidget(QLabel("✅",styleSheet="font-size:14px;"))

        # ON/OFF toggle
        toggle = QPushButton("ВКЛ" if enabled else "ВЫКЛ")
        toggle.setFixedSize(54, 26)
        toggle.setCheckable(True); toggle.setChecked(enabled)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:1px solid #374151; color:#6B7280;
                font-size:9px; font-weight:700; letter-spacing:1px; border-radius:5px; }}
            QPushButton:checked {{ background:{S.success}22; border-color:{S.success}; color:{S.success}; }}
        """)
        toggle.toggled.connect(lambda checked, c=code, t=toggle: self._toggle_league(c, checked, t))
        row_layout.addWidget(toggle)

        # Click to open analysis
        row.mousePressEvent = lambda e, l=lg: self._on_league_click(l)
        return row

    @staticmethod
    def _best_market(bt: dict) -> tuple:
        """Returns (market_key, roi) for the best ROI market."""
        best_key, best_roi = None, -999
        for key in ["corners","cards","goals"]:
            if key in bt:
                roi = bt[key].get("roi", -999)
                if roi > best_roi:
                    best_roi, best_key = roi, key
        if best_key is None:
            return None, 0.0
        return best_key, best_roi

    @staticmethod
    def _best_winrate(bt: dict) -> float:
        vals = [bt[k].get("winrate",0) for k in ["corners","cards","goals"] if k in bt]
        return max(vals) if vals else 0.0

    def _toggle_league(self, code: str, enabled: bool, btn: QPushButton):
        Config.set_league_enabled(code, enabled)
        btn.setText("ВКЛ" if enabled else "ВЫКЛ")
        logging.info(f"League {code} {'enabled' if enabled else 'disabled'}")

    def _on_league_click(self, lg: dict):
        if not lg.get("enabled", False):
            return   # don't open disabled leagues
        self.league_selected.emit(lg)

    def _open_update_dialog(self):
        from gui.update_dialog import UpdateDialog
        UpdateDialog(self).exec()

    # ── Global stats ──────────────────────────────────────────────────────────

    def _refresh_global_stats(self):
        stats = self.db.get_stats()
        bank  = self.db.get_bankroll()
        roi   = stats["roi"]
        self._g_bank.set_value(f"{bank['amount']:,} ₽")
        self._g_roi.set_value(f"{'+' if roi>=0 else ''}{roi:.1f}%",
                               S.success if roi >= 0 else S.error)
        self._g_wr.set_value(f"{stats['winrate']:.0f}%")
        self._g_bets.set_value(str(stats["total"]))

    # ── Public ────────────────────────────────────────────────────────────────

    def on_league_loaded(self, code: str, payload: dict):
        self._payloads[code] = payload
        self._rebuild_leagues()

    def get_payload(self, code: str):
        return self._payloads.get(code)

    def refresh_stats(self):
        self._refresh_global_stats()
        self._rebuild_leagues()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
            elif item.layout(): LeagueSelectorScreen._clear_layout(item.layout())
