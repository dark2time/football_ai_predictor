"""
Update dialog v1.0 — PyQt6
GitHub Releases integration
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from core.config import Config
from core.updater import check_for_update, download_and_install, restart_app
from gui.styles import S


class _CheckWorker(QThread):
    result = pyqtSignal(object)
    def run(self):
        url  = Config.version_check_url()
        info = check_for_update(url)
        self.result.emit(info)


class _InstallWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool)
    def __init__(self, info):
        super().__init__()
        self._info = info
    def run(self):
        ok = download_and_install(self._info, progress_cb=self.progress.emit)
        self.finished.emit(ok)


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Проверка обновлений")
        self.setModal(True)
        self.setFixedWidth(480)
        self.setStyleSheet("background:#0B0F1A;")
        self._update_info = None
        self._build()
        self._check()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)

        # Header
        title = QLabel("Обновление приложения")
        title.setStyleSheet("color:#E2E8F0;font-size:18px;font-weight:700;")
        root.addWidget(title)

        self._ver_lbl = QLabel(f"Текущая версия: v{Config.current_version()}")
        self._ver_lbl.setStyleSheet(f"color:{S.muted};font-size:12px;")
        root.addWidget(self._ver_lbl)

        # Source info
        source = QLabel("Источник обновлений: GitHub Releases")
        source.setStyleSheet(f"color:{S.dim};font-size:11px;")
        root.addWidget(source)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:#1F2937;margin:4px 0;")
        root.addWidget(sep)

        # Status
        self._status = QLabel("🔍 Проверяю обновления на GitHub…")
        self._status.setStyleSheet(f"color:{S.info};font-size:13px;font-weight:600;")
        self._status.setWordWrap(True)
        root.addWidget(self._status)

        # New version info (hidden until update found)
        self._new_ver_frame = QFrame()
        self._new_ver_frame.setStyleSheet(
            f"background:#0B1A12;border:1px solid {S.success}44;border-radius:8px;")
        nv_layout = QVBoxLayout(self._new_ver_frame)
        nv_layout.setContentsMargins(14, 12, 14, 12)
        self._new_ver_lbl = QLabel("")
        self._new_ver_lbl.setStyleSheet(f"color:{S.success};font-size:14px;font-weight:700;")
        nv_layout.addWidget(self._new_ver_lbl)
        self._data_note = QLabel("⚠ Ваши данные (CSV, статистика, настройки) будут сохранены.")
        self._data_note.setStyleSheet(f"color:{S.muted};font-size:11px;")
        nv_layout.addWidget(self._data_note)
        self._new_ver_frame.hide()
        root.addWidget(self._new_ver_frame)

        # Progress bar
        self._bar = QProgressBar()
        self._bar.setRange(0, 100); self._bar.setValue(0)
        self._bar.setFixedHeight(6); self._bar.setTextVisible(False)
        self._bar.setStyleSheet(S.progress_bar())
        root.addWidget(self._bar)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)

        self._install_btn = QPushButton("⬇  Установить обновление")
        self._install_btn.setFixedHeight(46)
        self._install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._install_btn.setStyleSheet(S.btn_solid())
        self._install_btn.hide()
        self._install_btn.clicked.connect(self._install)
        btn_row.addWidget(self._install_btn, 2)

        self._close_btn = QPushButton("Закрыть")
        self._close_btn.setFixedHeight(46)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet(S.btn_ghost())
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn, 1)

        root.addLayout(btn_row)

    def _check(self):
        self._check_worker = _CheckWorker()
        self._check_worker.result.connect(self._on_check_result)
        self._check_worker.start()

    def _on_check_result(self, info):
        if info:
            self._update_info = info
            new_ver = info.get("version", "?")
            self._status.setText(f"✅ Доступна новая версия!")
            self._status.setStyleSheet(f"color:{S.success};font-size:13px;font-weight:600;")
            self._new_ver_lbl.setText(f"v{Config.current_version()}  →  v{new_ver}")
            self._new_ver_frame.show()
            self._install_btn.show()
        else:
            self._status.setText("✅ У вас установлена актуальная версия.")
            self._status.setStyleSheet(f"color:{S.success};font-size:13px;")
            self._bar.setValue(100)

    def _install(self):
        if not self._update_info:
            return
        self._install_btn.setEnabled(False)
        self._close_btn.setEnabled(False)
        self._status.setText("Загружаю обновление…")
        self._status.setStyleSheet(f"color:{S.info};font-size:13px;")

        self._inst_worker = _InstallWorker(self._update_info)
        self._inst_worker.progress.connect(
            lambda p, m: (self._bar.setValue(p), self._status.setText(m)))
        self._inst_worker.finished.connect(self._on_installed)
        self._inst_worker.start()

    def _on_installed(self, ok: bool):
        if ok:
            new_ver = self._update_info.get("version","?")
            self._status.setText(f"✅ Версия v{new_ver} установлена! Перезапуск через 2 секунды…")
            self._status.setStyleSheet(f"color:{S.success};font-size:13px;font-weight:600;")
            self._bar.setValue(100)
            QTimer.singleShot(2000, restart_app)
        else:
            self._status.setText("❌ Ошибка при установке обновления. Проверьте подключение к интернету.")
            self._status.setStyleSheet(f"color:{S.error};font-size:13px;")
            self._install_btn.setEnabled(True)
            self._close_btn.setEnabled(True)
