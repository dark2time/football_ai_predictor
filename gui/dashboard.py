"""Dashboard v3 — PyQt6."""

import gc
import logging
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QFrame, QScrollArea, QSplitter, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QColor, QFont

from core.config import Config
from core.database import Database
from gui.styles import S
from gui.widgets import StatCard, SectionLabel, h_sep, v_sep
from gui.load_worker import LoadWorker
from gui.match_analysis import MatchAnalysisDialog
from gui.betting_log import BettingLogDialog
from gui.settings_dialog import SettingsDialog


class DashboardScreen(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._worker   = None
        self._df       = pd.DataFrame()
        self._fixtures = pd.DataFrame()
        self._plugins  = {}
        self._league   = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0,0,0,0)
        root.setSpacing(0)

        self._loading = self._build_loading()
        root.addWidget(self._loading)

        self._content = QWidget()
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0,0,0,0)
        cl.setSpacing(0)
        cl.addWidget(self._build_header())
        cl.addWidget(self._build_stats_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet("QSplitter::handle { background: #1F2937; }")
        splitter.addWidget(self._build_main_area())
        splitter.addWidget(self._build_sidebar())
        splitter.setSizes([920, 260])
        cl.addWidget(splitter, 1)

        root.addWidget(self._content)
        self._content.hide()

    # ── Loading ───────────────────────────────────────────────────────────────

    def _build_loading(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        self._lf = QLabel("")
        self._lf.setStyleSheet("font-size: 48px;")
        self._lf.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lf)
        self._ll = QLabel("")
        self._ll.setStyleSheet(f"color: {S.dim}; font-size: 10px; letter-spacing: 3px;")
        self._ll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._ll)
        self._lt = QLabel("")
        self._lt.setStyleSheet("color: #E2E8F0; font-size: 24px; font-weight: 700;")
        self._lt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lt)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(380)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(S.progress_bar())
        layout.addWidget(self._progress, alignment=Qt.AlignmentFlag.AlignCenter)

        self._step_lbl = QLabel("Инициализация…")
        self._step_lbl.setStyleSheet(f"color: {S.muted}; font-size: 12px;")
        self._step_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._step_lbl)
        return w

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        w = QFrame()
        w.setStyleSheet(f"background: #111827; border-bottom: 1px solid #1F2937;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(28, 14, 28, 14)
        layout.setSpacing(16)

        back = QPushButton("← Сменить лигу")
        back.setFixedHeight(36)
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setStyleSheet(S.btn_ghost())
        back.clicked.connect(self._on_back)
        layout.addWidget(back)

        self._hf = QLabel("")
        self._hf.setStyleSheet("font-size: 22px;")
        layout.addWidget(self._hf)

        col = QVBoxLayout(); col.setSpacing(2)
        self._hc = QLabel("")
        self._hc.setStyleSheet(f"color: {S.dim}; font-size: 9px; letter-spacing: 2px; font-weight: 600;")
        col.addWidget(self._hc)
        self._hl = QLabel("")
        self._hl.setStyleSheet("color: #E2E8F0; font-size: 16px; font-weight: 700;")
        col.addWidget(self._hl)
        layout.addLayout(col)
        layout.addStretch()

        self._hbank = QLabel("")
        self._hbank.setStyleSheet("color: #E2E8F0; font-size: 18px; font-weight: 700;")
        layout.addWidget(self._hbank)

        self._hpend = QLabel("")
        self._hpend.setStyleSheet(f"color: {S.warning}; font-size: 11px; font-weight: 600;")
        layout.addWidget(self._hpend)

        log_btn = QPushButton("📋 Журнал")
        log_btn.setFixedHeight(34); log_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        log_btn.setStyleSheet(S.btn_ghost()); log_btn.clicked.connect(self._open_log)
        layout.addWidget(log_btn)

        set_btn = QPushButton("⚙ Настройки")
        set_btn.setFixedHeight(34); set_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        set_btn.setStyleSheet(S.btn_ghost()); set_btn.clicked.connect(self._open_settings)
        layout.addWidget(set_btn)
        return w

    # ── Stats bar ─────────────────────────────────────────────────────────────

    def _build_stats_bar(self):
        w = QFrame()
        w.setStyleSheet("border-bottom: 1px solid #1F2937;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(28, 12, 28, 12)
        layout.setSpacing(0)

        self._stat_cards = {}
        items = [
            ("roi",     "ROI лиги",  "—", S.success),
            ("wr",      "Winrate",   "—", S.info),
            ("bets",    "Ставок",    "0", "#E2E8F0"),
            ("pending", "Ожидают",   "0", S.warning),
        ]
        for i, (key, lbl, default, color) in enumerate(items):
            card = StatCard(lbl, default, color)
            self._stat_cards[key] = card
            layout.addWidget(card)
            if i < len(items)-1:
                layout.addWidget(v_sep())
        layout.addStretch()
        return w

    # ── Main area (tabs) ──────────────────────────────────────────────────────

    def _build_main_area(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(28, 0, 12, 0)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.setStyleSheet(S.tab_widget())
        tabs.addTab(self._build_schedule_tab(), "Расписание")
        tabs.addTab(self._build_history_tab(), "История")
        layout.addWidget(tabs, 1)
        return w

    def _build_schedule_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)

        # Filter bar
        filter_row = QHBoxLayout()
        self._value_btn = QPushButton("⭐ Только Value Bets")
        self._value_btn.setCheckable(True)
        self._value_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._value_btn.setStyleSheet("""
            QPushButton { background: transparent; border: 1px solid #374151; color: #6B7280;
                font-size: 10px; border-radius: 6px; padding: 6px 14px; font-weight: 600; }
            QPushButton:checked { background: rgba(0,200,150,0.12); border-color: #00C896; color: #00C896; }
        """)
        self._value_btn.toggled.connect(lambda _: self._populate_schedule())
        filter_row.addWidget(self._value_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self._sched_table = self._make_table(
            ["ДАТА", "ВРЕМЯ", "ХОЗЯЕВА", "ГОСТИ", ""],
            [110, 70, 0, 0, 90]
        )
        layout.addWidget(self._sched_table, 1)
        return w

    def _build_history_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 12, 0, 0)
        self._hist_table = self._make_table(
            ["ДАТА", "ХОЗЯЕВА", "ГОСТИ", "СЧЁТ", "УГЛ", "ЖК"],
            [110, 0, 0, 70, 60, 60]
        )
        layout.addWidget(self._hist_table, 1)
        return w

    def _make_table(self, headers, widths):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        t.setShowGrid(False)
        t.setStyleSheet(S.table())
        t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        for i, w in enumerate(widths):
            if w == 0:
                t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                t.setColumnWidth(i, w)
        return t

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        w = QWidget()
        w.setFixedWidth(260)
        w.setStyleSheet("border-left: 1px solid #1F2937;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 20, 16, 16)
        layout.setSpacing(10)
        layout.addWidget(SectionLabel("Плагины"))

        self._plugin_frames = {}
        for key in ["corners", "cards", "goals", "outcome"]:
            f = self._make_plugin_card(key)
            self._plugin_frames[key] = f
            layout.addWidget(f)

        layout.addSpacing(8)
        layout.addWidget(SectionLabel("Режим"))
        self._mode_frame = QFrame()
        self._mode_frame.setStyleSheet(S.card())
        ml = QVBoxLayout(self._mode_frame)
        ml.setContentsMargins(12, 10, 12, 10)
        self._mode_lbl = QLabel("⚖ Консервативный")
        self._mode_lbl.setStyleSheet(f"color: {S.info}; font-size: 12px; font-weight: 700;")
        ml.addWidget(self._mode_lbl)
        self._mode_pct = QLabel("2% банка / ставка")
        self._mode_pct.setStyleSheet(f"color: {S.dim}; font-size: 10px;")
        ml.addWidget(self._mode_pct)
        layout.addWidget(self._mode_frame)
        layout.addStretch()
        return w

    def _make_plugin_card(self, key):
        cfg   = Config.plugins().get(key, {})
        color = cfg.get("color", S.success)
        f = QFrame()
        f.setStyleSheet(S.card())
        layout = QVBoxLayout(f)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        name_lbl = QLabel(f"{cfg.get('emoji','')}  {cfg.get('name','')}")
        name_lbl.setStyleSheet("color: #E2E8F0; font-size: 12px; font-weight: 600;")
        top.addWidget(name_lbl)
        top.addStretch()
        toggle = QPushButton("ВКЛ" if cfg.get("enabled") else "ВЫКЛ")
        toggle.setFixedSize(46, 22)
        toggle.setCheckable(True)
        toggle.setChecked(cfg.get("enabled", False))
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: 1px solid #374151; color: #6B7280;
                font-size: 8px; font-weight: 700; letter-spacing: 1px; border-radius: 4px; }}
            QPushButton:checked {{ background: {color}22; border-color: {color}; color: {color}; }}
        """)
        toggle.toggled.connect(lambda checked, k=key: self._toggle_plugin(k, checked))
        top.addWidget(toggle)
        layout.addLayout(top)

        acc_lbl = QLabel("Точность: —")
        acc_lbl.setStyleSheet(f"color: {S.muted}; font-size: 10px;")
        layout.addWidget(acc_lbl)
        acc_bar = QProgressBar()
        acc_bar.setRange(0, 100); acc_bar.setValue(0)
        acc_bar.setFixedHeight(5); acc_bar.setTextVisible(False)
        acc_bar.setStyleSheet(S.progress_bar(color))
        layout.addWidget(acc_bar)
        roi_lbl = QLabel("ROI: —")
        roi_lbl.setStyleSheet(f"color: {S.muted}; font-size: 10px;")
        layout.addWidget(roi_lbl)

        f._acc_lbl = acc_lbl
        f._acc_bar = acc_bar
        f._roi_lbl = roi_lbl
        return f

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_league(self, league_data: dict, cached_payload: dict | None = None):
        if not self._df.empty:
            del self._df; gc.collect()
        self._league = league_data
        self._df     = pd.DataFrame()
        self._lf.setText(league_data.get("flag", ""))
        self._ll.setText(league_data.get("name","").upper())
        self._lt.setText(league_data.get("league",""))
        self._hf.setText(league_data.get("flag",""))
        self._hc.setText(league_data.get("name","").upper())
        self._hl.setText(league_data.get("league",""))
        self._progress.setValue(0)
        self._step_lbl.setText("Подготовка…")
        self._content.hide(); self._loading.show()

        if cached_payload:
            self._on_loaded(cached_payload)
            return

        if self._worker and self._worker.isRunning():
            self._worker.abort(); self._worker.wait()
        self._worker = LoadWorker(league_data, Config.plugins())
        self._worker.progress.connect(lambda p, m: (self._progress.setValue(p), self._step_lbl.setText(m)))
        self._worker.finished.connect(self._on_loaded)
        self._worker.error.connect(lambda msg: (QMessageBox.critical(self,"Ошибка",msg), self._step_lbl.setText(f"Ошибка: {msg}")))
        self._worker.start()

    def _on_loaded(self, payload):
        self._df       = payload["df"]
        self._fixtures = payload["fixtures"]
        self._plugins  = payload["plugins"]
        self._populate_schedule()
        self._populate_history()
        self._refresh_sidebar()
        self._refresh_stats()
        self._loading.hide(); self._content.show()

    # ── Populate tables ───────────────────────────────────────────────────────

    def _populate_schedule(self):
        from core.value_filter import passes_filter, value_pct
        ASSUMED_ODDS = 1.88

        t = self._sched_table
        t.setRowCount(0)
        if self._fixtures.empty:
            t.setRowCount(1)
            t.setItem(0, 0, self._cell("Расписание недоступно", S.muted))
            return

        show_value_only = self._value_btn.isChecked()
        rows_to_show = []

        for _, row in self._fixtures.iterrows():
            home = str(row.get("HomeTeam",""))
            away = str(row.get("AwayTeam",""))

            # Quick value check using enabled plugins
            is_value = False
            best_prob = 0.0
            for key, plugin in self._plugins.items():
                if not plugin.enabled or self._df.empty:
                    continue
                try:
                    pred = plugin.predict(self._df, home, away,
                                          league_code=self._league.get("code",""))
                    if pred:
                        prob = pred.get("probability", 0)
                        if passes_filter(prob, ASSUMED_ODDS):
                            is_value = True
                        if prob > best_prob:
                            best_prob = prob
                except Exception:
                    pass

            if show_value_only and not is_value:
                continue
            rows_to_show.append((row, is_value, best_prob))

        t.setRowCount(len(rows_to_show))
        for i, (row, is_value, best_prob) in enumerate(rows_to_show):
            date_str = str(row["Date"])[:10]
            time_str = str(row.get("Time",""))[:5] or "—"
            home     = str(row.get("HomeTeam",""))
            away     = str(row.get("AwayTeam",""))

            t.setItem(i, 0, self._cell(date_str, S.muted))
            t.setItem(i, 1, self._cell(time_str, S.dim))

            name_text = ("⭐ " if is_value else "") + home
            t.setItem(i, 2, self._cell(name_text, S.success if is_value else "#E2E8F0", bold=True))
            t.setItem(i, 3, self._cell(away, "#9CA3AF"))
            t.setRowHeight(i, 52)

            btn = QPushButton("Анализ →")
            btn.setFixedSize(88, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(S.btn_primary(S.success if is_value else "#4A9EFF"))
            btn.clicked.connect(lambda _, h=home, a=away, r=row: self._open_analysis(h, a, r))
            t.setCellWidget(i, 4, btn)

    def _populate_history(self):
        t = self._hist_table
        t.setRowCount(0)
        if self._df.empty: return
        recent = self._df.tail(60).sort_values("Date", ascending=False)
        t.setRowCount(len(recent))
        for i, (_, row) in enumerate(recent.iterrows()):
            fthg = int(row.get("FTHG") or 0)
            ftag = int(row.get("FTAG") or 0)
            hc   = int(row.get("HC")   or 0)
            ac   = int(row.get("AC")   or 0)
            hy   = int(row.get("HY")   or 0)
            ay   = int(row.get("AY")   or 0)
            t.setItem(i, 0, self._cell(str(row["Date"])[:10], S.dim))
            t.setItem(i, 1, self._cell(str(row.get("HomeTeam","")), "#D1D5DB"))
            t.setItem(i, 2, self._cell(str(row.get("AwayTeam","")), "#9CA3AF"))
            t.setItem(i, 3, self._cell(f"{fthg}–{ftag}", "#E2E8F0", bold=True))
            t.setItem(i, 4, self._cell(str(hc+ac), S.info))
            t.setItem(i, 5, self._cell(str(hy+ay), S.warning))
            t.setRowHeight(i, 48)

    def _refresh_sidebar(self):
        for key, plugin in self._plugins.items():
            f = self._plugin_frames.get(key)
            if f is None: continue
            f._acc_lbl.setText(f"Точность: {plugin.accuracy:.0f}%")
            f._acc_bar.setValue(int(plugin.accuracy))
            roi_color = S.success if plugin.roi >= 0 else S.error
            f._roi_lbl.setText(f"ROI: {'+' if plugin.roi>=0 else ''}{plugin.roi:.0f}%")
            f._roi_lbl.setStyleSheet(f"color: {roi_color}; font-size: 10px; font-weight: 600;")

    def _refresh_stats(self):
        stats = self.db.get_stats()
        br    = self.db.get_bankroll()
        code  = self._league.get("code","")
        lg    = stats["by_league"].get(code,{})

        roi = lg.get("roi", 0)
        self._stat_cards["roi"].set_value(f"{'+' if roi>=0 else ''}{roi:.1f}%",
                                           S.success if roi>=0 else S.error)
        self._stat_cards["wr"].set_value(f"{lg.get('winrate',0):.0f}%")
        self._stat_cards["bets"].set_value(str(lg.get("total",0)))
        pend = len(self.db.get_pending_bets())
        self._stat_cards["pending"].set_value(str(pend))

        self._hbank.setText(f"{br['amount']:,} ₽")
        self._hpend.setText(f"⏳ {pend}" if pend else "")

        mode = br["mode"]
        self._mode_lbl.setText("⚖ Консервативный" if mode=="conservative" else "⚡ Агрессивный")
        self._mode_pct.setText("2% банка / ставка" if mode=="conservative" else "5% банка / ставка")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _open_analysis(self, home, away, row):
        dlg = MatchAnalysisDialog(home=home, away=away, match_row=row,
                                  df_history=self._df, plugins=self._plugins,
                                  db=self.db, league=self._league, parent=self)
        dlg.exec()
        self._refresh_stats()

    def _open_log(self):
        BettingLogDialog(self.db, self).exec()
        self._refresh_stats()

    def _open_settings(self):
        SettingsDialog(self.db, self).exec()
        self._refresh_stats()

    def _on_back(self):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
        del self._df; gc.collect()
        self._df = pd.DataFrame()
        self.back_requested.emit()

    def _toggle_plugin(self, key, checked):
        if key in self._plugins:
            self._plugins[key].enabled = checked
        cfg = Config.plugins()
        if key in cfg:
            cfg[key]["enabled"] = checked
            Config.set(cfg, "plugins")

    @staticmethod
    def _cell(text, color="#9CA3AF", bold=False):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        if bold:
            f = item.font(); f.setBold(True); item.setFont(f)
        return item
