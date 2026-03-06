"""Disclaimer screen v3 — PyQt6."""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFrame
from PyQt6.QtCore import pyqtSignal, Qt
from gui.styles import S


class DisclaimerScreen(QWidget):
    accepted = pyqtSignal()

    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setFixedWidth(500)
        card.setStyleSheet(f"background: {S.bg_card}; border: 1px solid {S.border2}; border-radius: 12px;")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(44, 48, 44, 40)
        layout.setSpacing(16)

        warn = QLabel("⚠  ВНИМАНИЕ")
        warn.setStyleSheet(f"color: {S.error}; font-size: 10px; letter-spacing: 3px; font-weight: 700;")
        layout.addWidget(warn)

        title = QLabel("Football AI\nPredictor Pro")
        title.setStyleSheet("color: #E2E8F0; font-size: 28px; font-weight: 700; line-height: 1.2;")
        layout.addWidget(title)

        ver = QLabel("v3.0")
        ver.setStyleSheet(f"color: {S.success}; font-size: 11px; font-weight: 600;")
        layout.addWidget(ver)

        layout.addSpacing(8)

        body = QLabel(
            "Эта программа является инструментом для анализа статистики "
            "футбольных матчей. Она НЕ ГАРАНТИРУЕТ прибыль.\n\n"
            "Ставки на спорт связаны с финансовым риском. Вы можете "
            "потерять все вложенные средства. Используйте только деньги, "
            "которые готовы потерять.\n\n"
            "Убедитесь, что ставки разрешены в вашей юрисдикции."
        )
        body.setStyleSheet(f"color: {S.muted}; font-size: 12px; line-height: 1.7;")
        body.setWordWrap(True)
        layout.addWidget(body)

        layout.addSpacing(16)

        accept_btn = QPushButton("✓  Понимаю и принимаю риски")
        accept_btn.setFixedHeight(48)
        accept_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        accept_btn.setStyleSheet(S.btn_solid())
        accept_btn.clicked.connect(self.accepted.emit)
        layout.addWidget(accept_btn)

        exit_btn = QPushButton("Выход из программы")
        exit_btn.setFixedHeight(36)
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet(S.btn_ghost())
        exit_btn.clicked.connect(lambda: __import__("sys").exit(0))
        layout.addWidget(exit_btn)

        outer.addWidget(card)
