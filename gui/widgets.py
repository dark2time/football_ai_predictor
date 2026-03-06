"""
Reusable widgets for v3 UI.
"""

from PyQt6.QtWidgets import (
    QWidget, QLabel, QFrame, QProgressBar, QHBoxLayout, QVBoxLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from gui.styles import S


def h_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("color: #1F2937;")
    return f


def v_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color: #1F2937;")
    return f


class StatCard(QFrame):
    """Small stat display card: label + big number."""
    def __init__(self, label: str, value: str = "—", color: str = "#E2E8F0", parent=None):
        super().__init__(parent)
        self.setStyleSheet(S.card())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        self._lbl = QLabel(label.upper())
        self._lbl.setStyleSheet(f"color: {S.dim}; font-size: 9px; letter-spacing: 1.5px; font-weight: 600;")
        layout.addWidget(self._lbl)

        self._val = QLabel(value)
        self._val.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700;")
        layout.addWidget(self._val)

    def set_value(self, value: str, color: str | None = None):
        self._val.setText(value)
        if color:
            self._val.setStyleSheet(f"color: {color}; font-size: 22px; font-weight: 700;")


class MiniProgress(QWidget):
    """Label + thin progress bar."""
    def __init__(self, label: str, value: int = 0, color: str = "#00C896", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self._lbl = QLabel(label)
        self._lbl.setStyleSheet(f"color: {S.muted}; font-size: 10px;")
        layout.addWidget(self._lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(value)
        self._bar.setFixedHeight(5)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(S.progress_bar(color))
        layout.addWidget(self._bar)

    def update(self, label: str, value: int, color: str | None = None):
        self._lbl.setText(label)
        self._bar.setValue(value)
        if color:
            self._bar.setStyleSheet(S.progress_bar(color))


class SectionLabel(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(f"color: {S.dim}; font-size: 9px; letter-spacing: 2px; font-weight: 600; margin-top: 8px;")


class ValueBadge(QLabel):
    def __init__(self, text: str, color: str = "#00C896", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(S.tag(color))
