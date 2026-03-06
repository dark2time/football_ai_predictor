"""Match Analysis dialog v3 — PyQt6."""

import logging
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QLineEdit, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from parsers.oddsportal_parser import fetch_odds
from core.database import Database
from gui.styles import S
from gui.widgets import h_sep


class OddsWorker(QThread):
    finished = pyqtSignal(object)
    def __init__(self, home, away, date_str):
        super().__init__()
        self.home, self.away, self.date_str = home, away, date_str
    def run(self):
        try:
            self.finished.emit(fetch_odds(self.home, self.away, self.date_str))
        except Exception:
            self.finished.emit(None)


class MatchAnalysisDialog(QDialog):

    def __init__(self, home, away, match_row, df_history, plugins, db, league, parent=None):
        super().__init__(parent)
        self.home, self.away = home, away
        self.match_row  = match_row
        self.df_history = df_history
        self.plugins    = plugins
        self.db         = db
        self.league     = league
        self._predictions = {}

        self.setWindowTitle(f"{home} vs {away}")
        self.setModal(True)
        self.setMinimumWidth(640)
        self.setMinimumHeight(640)
        self.setStyleSheet(f"background: #0B0F1A;")
        self._build()
        self._run_analysis()
        self._start_odds_fetch()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # Header
        date_str = str(self.match_row.get("Date", ""))[:10]
        time_str = str(self.match_row.get("Time", ""))[:5]
        sub = QLabel(f"{self.league.get('flag','')} {self.league.get('league','')}  ·  {date_str}  {time_str}")
        sub.setStyleSheet(f"color: {S.dim}; font-size: 10px; letter-spacing: 1px;")
        root.addWidget(sub)
        root.addSpacing(6)
        title = QLabel(f"{self.home}  —  {self.away}")
        title.setStyleSheet("color: #E2E8F0; font-size: 22px; font-weight: 700;")
        root.addWidget(title)
        root.addSpacing(20)
        root.addWidget(h_sep())
        root.addSpacing(16)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(S.scroll_area())
        self._scroll_w = QWidget()
        self._pred_layout = QVBoxLayout(self._scroll_w)
        self._pred_layout.setSpacing(12)
        scroll.setWidget(self._scroll_w)
        root.addWidget(scroll, 1)

        root.addSpacing(16)

        # Odds row
        odds_row = QHBoxLayout()
        odds_lbl = QLabel("Коэффициент:")
        odds_lbl.setStyleSheet(f"color: {S.muted}; font-size: 12px;")
        odds_row.addWidget(odds_lbl)
        self._odds_input = QLineEdit()
        self._odds_input.setPlaceholderText("напр. 1.90")
        self._odds_input.setFixedWidth(160)
        self._odds_input.setFixedHeight(36)
        self._odds_input.setStyleSheet(S.input())
        odds_row.addWidget(self._odds_input)
        self._odds_status = QLabel("🔄 Поиск…")
        self._odds_status.setStyleSheet(f"color: {S.dim}; font-size: 11px; margin-left: 10px;")
        odds_row.addWidget(self._odds_status)
        odds_row.addStretch()
        root.addLayout(odds_row)
        root.addSpacing(16)

        # Stake info
        br    = self.db.get_bankroll()
        mode  = br["mode"]
        bank  = br["amount"]
        pct   = 0.02 if mode == "conservative" else 0.05
        self._stake = max(500, round(bank * pct / 500) * 500)
        self._stake = min(self._stake, int(bank * 0.05))
        stake_lbl = QLabel(f"💰 Рекомендуемая ставка:  <b style='color:#E2E8F0; font-size:15px;'>{self._stake:,} ₽</b>"
                           f"  <span style='color:{S.dim}; font-size:10px;'>({int(pct*100)}% банка · {mode})</span>")
        stake_lbl.setStyleSheet(f"color: {S.muted}; font-size: 12px;")
        root.addWidget(stake_lbl)
        root.addSpacing(16)

        # Buttons
        btn_row = QHBoxLayout()
        self._bet_btn = QPushButton("✓  ПОСТАВИЛ")
        self._bet_btn.setFixedHeight(48)
        self._bet_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bet_btn.setStyleSheet(S.btn_solid(S.success))
        self._bet_btn.clicked.connect(self._place_bet)
        skip_btn = QPushButton("Пропустить")
        skip_btn.setFixedHeight(48)
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.setStyleSheet(S.btn_ghost())
        skip_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._bet_btn, 2)
        btn_row.addWidget(skip_btn, 1)
        root.addLayout(btn_row)

    def _run_analysis(self):
        code    = self.league.get("code", "")
        referee = str(self.match_row.get("Referee", "") or "")
        for key, plugin in self.plugins.items():
            if not plugin.enabled: continue
            try:
                pred = plugin.predict(self.df_history, self.home, self.away,
                                      referee, league_code=code)
                if pred:
                    self._predictions[key] = pred
            except Exception as e:
                logging.warning(f"Analysis {key}: {e}")
        self._render()

    def _render(self):
        while self._pred_layout.count():
            item = self._pred_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        if not self._predictions:
            lbl = QLabel("Недостаточно данных для прогноза.")
            lbl.setStyleSheet(f"color: {S.muted}; font-size: 13px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._pred_layout.addWidget(lbl)
            return

        try:
            manual_odds = float(self._odds_input.text() or 0)
        except ValueError:
            manual_odds = 0

        for key, pred in self._predictions.items():
            plugin = self.plugins[key]
            self._pred_layout.addWidget(self._make_pred_card(plugin, pred, manual_odds))
        self._pred_layout.addStretch()

    def _make_pred_card(self, plugin, pred, manual_odds):
        color = plugin.color
        prob  = pred.get("probability", 0)
        rec   = pred.get("recommendation", "—")

        is_value = False
        from core.value_filter import passes_filter, compute_value, value_pct as _vpct
        if manual_odds > 1.0:
            is_value = passes_filter(prob, manual_odds)
            _value   = compute_value(prob, manual_odds)
            _vpct_v  = _vpct(prob, manual_odds)
        else:
            is_value = prob >= 0.65
            _value   = prob * 1.88
            _vpct_v  = _value - 1.0

        border = color if is_value else "#1F2937"
        card = QFrame()
        card.setStyleSheet(f"background: #111827; border: 1px solid {border}; border-radius: 10px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        # Plugin header
        hdr = QHBoxLayout()
        ph = QLabel(f"{plugin.emoji}  {plugin.name.upper()}")
        ph.setStyleSheet(f"color: {color}; font-size: 10px; letter-spacing: 1.5px; font-weight: 700;")
        hdr.addWidget(ph)
        hdr.addStretch()
        if is_value:
            tag = QLabel("✅  VALUE BET")
            tag.setStyleSheet(S.tag(S.success))
            hdr.addWidget(tag)
        layout.addLayout(hdr)

        # Recommendation
        rec_lbl = QLabel(rec)
        rec_lbl.setStyleSheet("color: #F9FAFB; font-size: 20px; font-weight: 700;")
        layout.addWidget(rec_lbl)

        # Stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(28)
        for label, value, clr in [("ВЕРОЯТНОСТЬ", f"{prob:.0%}", color),
                                    ("СТАВКА", f"{self._stake:,} ₽", "#E2E8F0")]:
            col = QVBoxLayout()
            col.setSpacing(2)
            l = QLabel(label)
            l.setStyleSheet(f"color: {S.dim}; font-size: 9px; letter-spacing: 1.5px; font-weight: 600;")
            col.addWidget(l)
            v = QLabel(value)
            v.setStyleSheet(f"color: {clr}; font-size: 18px; font-weight: 700;")
            col.addWidget(v)
            stats_row.addLayout(col)
        if manual_odds > 1 and is_value:
            profit = int(self._stake * (manual_odds - 1))
            col = QVBoxLayout()
            l = QLabel("ПОТЕНЦИАЛЬНАЯ ПРИБЫЛЬ")
            l.setStyleSheet(f"color: {S.dim}; font-size: 9px; letter-spacing: 1.5px; font-weight: 600;")
            col.addWidget(l)
            v = QLabel(f"+{profit:,} ₽")
            v.setStyleSheet(f"color: {S.success}; font-size: 18px; font-weight: 700;")
            col.addWidget(v)
            stats_row.addLayout(col)
        stats_row.addStretch()
        layout.addLayout(stats_row)

        # Thresholds (compact)
        thresholds = pred.get("thresholds", [])
        if thresholds:
            rec_val = pred.get("threshold", 0)
            nearby  = [t for t in thresholds if abs(t.get("threshold", 0) - rec_val) <= 1.5][:4]
            for t in nearby:
                is_rec = abs(t.get("threshold", 0) - rec_val) < 0.1
                clr    = color if is_rec else (S.muted if t["prob"] >= 0.5 else S.dim)
                row = QHBoxLayout()
                vl  = QLabel(t["value"])
                vl.setStyleSheet(f"color: {clr}; font-size: 11px; font-weight: {'700' if is_rec else '400'}; min-width: 90px;")
                row.addWidget(vl)
                bar = QProgressBar()
                bar.setRange(0, 100); bar.setValue(int(t["prob"] * 100))
                bar.setFixedHeight(5); bar.setTextVisible(False)
                bar_color = color if t["prob"] >= 0.65 else (S.warning if t["prob"] >= 0.45 else S.error)
                bar.setStyleSheet(S.progress_bar(bar_color))
                row.addWidget(bar, 1)
                pl = QLabel(f"{t['prob']:.0%}")
                pl.setStyleSheet(f"color: {clr}; font-size: 11px; font-weight: 700; min-width: 40px;")
                row.addWidget(pl)
                ll = QLabel(t.get("label",""))
                ll.setStyleSheet(f"color: {S.dim}; font-size: 10px; min-width: 90px;")
                row.addWidget(ll)
                layout.addLayout(row)

        # Justification
        just = pred.get("justification","")
        if just:
            jl = QLabel(just)
            jl.setStyleSheet(f"color: {S.muted}; font-size: 11px;")
            jl.setWordWrap(True)
            layout.addWidget(jl)

        return card

    def _start_odds_fetch(self):
        date_str = str(self.match_row.get("Date",""))[:10]
        self._odds_worker = OddsWorker(self.home, self.away, date_str)
        self._odds_worker.finished.connect(self._on_odds)
        self._odds_worker.start()

    def _on_odds(self, result):
        if result:
            self._odds_status.setText("✅ Коэффициенты получены")
            for key, data in result.items():
                val = data.get("odds") if isinstance(data, dict) else data
                if val:
                    self._odds_input.setText(str(val))
                    break
            self._render()
        else:
            self._odds_status.setText("⚠ Введите коэффициент вручную")

    def _place_bet(self):
        if not self._predictions: return
        key    = next(iter(self._predictions))
        pred   = self._predictions[key]
        try:    odds = float(self._odds_input.text() or 1.90)
        except: odds = 1.90
        date_str = str(self.match_row.get("Date", datetime.now().date()))[:10]
        self.db.place_bet(
            date=date_str, league=self.league.get("code",""),
            match=f"{self.home} vs {self.away}",
            forecast=pred.get("recommendation","—"),
            odds=odds, stake=self._stake, plugin=key,
        )
        self.accept()
