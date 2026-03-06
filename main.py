"""
Football AI Predictor Pro v1.0
Entry point — PyQt6
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from gui.main_window import MainWindow
from core.database import Database
from core.config import Config


def setup_logging():
    os.makedirs("logs", exist_ok=True)
    fmt = "[%(asctime)s] %(levelname)s: %(message)s"
    handlers = [
        logging.FileHandler("logs/app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt,
                        datefmt="%Y-%m-%d %H:%M:%S", handlers=handlers)


def main():
    setup_logging()
    logging.info("Starting Football AI Predictor Pro v1.0")

    app = QApplication(sys.argv)
    app.setApplicationName("Football AI Predictor Pro")

    font = QFont("Inter", 11)
    if not font.exactMatch():
        font = QFont("Segoe UI", 11)
    app.setFont(font)

    app.setStyleSheet("""
        QWidget { background: #0B0F1A; color: #E2E8F0; font-size: 11px; }
        QScrollBar:vertical { background: #111827; width: 6px; border-radius: 3px; }
        QScrollBar::handle:vertical { background: #374151; border-radius: 3px; min-height: 20px; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal { background: #111827; height: 6px; }
        QScrollBar::handle:horizontal { background: #374151; border-radius: 3px; }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QToolTip { background: #1F2937; color: #E2E8F0; border: 1px solid #374151; padding: 6px; border-radius: 4px; }
    """)

    Config.load()
    db = Database()
    db.initialize()

    window = MainWindow(db)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
