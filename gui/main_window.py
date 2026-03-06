"""
Main window v1.0 — PyQt6
Handles: load-all, refresh-data, update check, auto-check bets.
"""

import logging
from PyQt6.QtWidgets import (
    QMainWindow, QStackedWidget, QMessageBox,
    QProgressBar, QLabel, QVBoxLayout, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from core.config import Config
from core.database import Database
from core.auto_checker import auto_check_results
from core.data_loader import DataLoader
from gui.disclaimer_screen import DisclaimerScreen
from gui.league_selector import LeagueSelectorScreen
from gui.dashboard import DashboardScreen
from gui.load_worker import AllLeaguesWorker
from gui.styles import S


class _RefreshWorker(QThread):
    """Downloads fresh CSV for all enabled leagues (no model retrain)."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal()

    def __init__(self, leagues):
        super().__init__()
        self._leagues = leagues

    def run(self):
        loader = DataLoader()
        total  = len(self._leagues)
        for i, lg in enumerate(self._leagues):
            code = lg["code"]
            self.progress.emit(int(i/total*90), f"Обновление {lg['league']}…")
            try:
                loader.load_league(code, force_full=False)
            except Exception as e:
                logging.warning(f"Refresh {code}: {e}")
        self.progress.emit(100, "Данные обновлены!")
        self.finished.emit()


class _LoadingOverlay(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:rgba(11,15,26,0.96);")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(18)
        self._lbl = QLabel("")
        self._lbl.setStyleSheet("color:#E2E8F0;font-size:20px;font-weight:700;")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._lbl)
        self._sub = QLabel("")
        self._sub.setStyleSheet(f"color:{S.muted};font-size:12px;")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._sub)
        self._bar = QProgressBar()
        self._bar.setFixedWidth(420); self._bar.setFixedHeight(6)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(S.progress_bar())
        layout.addWidget(self._bar, alignment=Qt.AlignmentFlag.AlignCenter)
        self._hint = QLabel("")
        self._hint.setStyleSheet(f"color:{S.dim};font-size:11px;margin-top:8px;")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint)

    def show_loading(self, title: str, hint: str = ""):
        self._lbl.setText(title)
        self._hint.setText(hint)
        self._bar.setValue(0)
        self._sub.setText("")
        self.show(); self.raise_()

    def update_progress(self, pct: int, msg: str):
        self._bar.setValue(pct)
        self._sub.setText(msg)


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._all_worker     = None
        self._refresh_worker = None
        self.setWindowTitle("Football AI Predictor Pro v1.0")
        self.setMinimumSize(1280, 800)
        self.resize(1460, 940)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.disclaimer = DisclaimerScreen()
        self.league_sel = LeagueSelectorScreen(db)
        self.dashboard  = DashboardScreen(db)

        self.stack.addWidget(self.disclaimer)  # 0
        self.stack.addWidget(self.league_sel)  # 1
        self.stack.addWidget(self.dashboard)   # 2

        self.disclaimer.accepted.connect(self._on_accepted)
        self.league_sel.league_selected.connect(self._on_league)
        self.league_sel.load_all_requested.connect(self._on_load_all)
        self.league_sel.refresh_requested.connect(self._on_refresh)
        self.dashboard.back_requested.connect(self._on_back)

        self._overlay = _LoadingOverlay(self)
        self._overlay.hide()

        self.stack.setCurrentIndex(0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._overlay.setGeometry(self.rect())

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_accepted(self):
        self.stack.setCurrentIndex(1)
        self._run_auto_check()

    def _on_league(self, lg: dict):
        code   = lg["code"]
        cached = self.league_sel.get_payload(code)
        self.dashboard.load_league(lg, cached_payload=cached)
        self.stack.setCurrentIndex(2)

    def _on_back(self):
        self.stack.setCurrentIndex(1)
        self.league_sel.refresh_stats()

    def _on_load_all(self):
        if self._all_worker and self._all_worker.isRunning():
            return
        enabled = Config.enabled_leagues()
        if not enabled:
            QMessageBox.information(self, "Нет лиг",
                "Включите хотя бы одну лигу с помощью переключателей ON/OFF.")
            return
        self._overlay.show_loading(
            "⚡  Загружаю включённые лиги…",
            f"Включено {len(enabled)} лиг · Первый запуск займёт несколько минут"
        )
        self._all_worker = AllLeaguesWorker(enabled, Config.plugins())
        self._all_worker.progress.connect(self._overlay.update_progress)
        self._all_worker.league_done.connect(self._on_league_done)
        self._all_worker.finished.connect(self._on_all_done)
        self._all_worker.error.connect(lambda m: logging.warning(f"AllLeagues: {m}"))
        self._all_worker.start()

    def _on_league_done(self, code: str, payload: dict):
        self.league_sel.on_league_loaded(code, payload)

    def _on_all_done(self, top_value: list):
        self._overlay.hide()
        self.league_sel.set_top_value(top_value)

    def _on_refresh(self):
        if self._refresh_worker and self._refresh_worker.isRunning():
            return
        enabled = Config.enabled_leagues()
        if not enabled:
            return
        self._overlay.show_loading(
            "🔄  Обновление данных…",
            "Скачиваю свежие CSV · Старые данные сохраняются"
        )
        self._refresh_worker = _RefreshWorker(enabled)
        self._refresh_worker.progress.connect(self._overlay.update_progress)
        self._refresh_worker.finished.connect(self._on_refresh_done)
        self._refresh_worker.start()

    def _on_refresh_done(self):
        self._overlay.hide()
        QMessageBox.information(self, "Готово",
            "Данные обновлены.\nНажмите «Загрузить все лиги» для переобучения моделей.")

    def _run_auto_check(self):
        pending = self.db.get_pending_bets()
        if not pending:
            return
        try:
            summary = auto_check_results(self.db)
            if summary.get("checked", 0) > 0:
                delta = summary.get("bank_delta", 0)
                bank  = self.db.get_bankroll()["amount"]
                dstr  = f"+{delta:,}" if delta >= 0 else f"{delta:,}"
                msg   = QMessageBox(self)
                msg.setWindowTitle("Проверка ставок")
                msg.setText(
                    f"Проверено {summary['checked']} ставок:\n"
                    f"✅ {summary['won']} выиграли\n"
                    f"❌ {summary['lost']} проиграли\n\n"
                    f"Банк: {bank:,} ₽ ({dstr} ₽)"
                )
                msg.exec()
        except Exception as e:
            logging.warning(f"Auto-check: {e}")
