"""Betting log dialog v3 — PyQt6."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QFrame, QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction

from core.database import Database
from gui.styles import S
from gui.widgets import StatCard


class BettingLogDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Журнал ставок")
        self.setModal(True)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(f"background: #0B0F1A;")
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Журнал ставок")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: 700;")
        hdr.addWidget(title)
        hdr.addStretch()
        QPushButton("✕", self).setFixedSize(32,32)
        close = QPushButton("✕")
        close.setFixedSize(32,32); close.setStyleSheet(S.btn_ghost())
        close.clicked.connect(self.accept)
        hdr.addWidget(close)
        root.addLayout(hdr)

        # Stat cards
        cards_row = QHBoxLayout(); cards_row.setSpacing(10)
        self._c_total   = StatCard("Всего",   "0")
        self._c_winrate = StatCard("Winrate", "0%",  S.info)
        self._c_roi     = StatCard("ROI",     "0%",  S.success)
        self._c_profit  = StatCard("Прибыль", "0 ₽", S.success)
        for c in [self._c_total, self._c_winrate, self._c_roi, self._c_profit]:
            cards_row.addWidget(c)
        cards_row.addStretch()
        root.addLayout(cards_row)

        # Filters
        f_row = QHBoxLayout(); f_row.setSpacing(8)
        f_row.addWidget(QLabel("Статус:"))
        self._filter = QComboBox()
        self._filter.addItems(["Все","Ожидание","Выиграл","Проиграл"])
        self._filter.setStyleSheet(S.input())
        self._filter.setFixedHeight(34)
        self._filter.currentIndexChanged.connect(self._load)
        f_row.addWidget(self._filter)
        f_row.addStretch()
        root.addLayout(f_row)

        # Table
        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(["ДАТА","МАТЧ","ПРОГНОЗ","КЭФ","СТАВКА","СТАТУС","ПРИБЫЛЬ"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for i, w in [(0,100),(3,60),(4,90),(5,70),(6,100)]:
            self._table.setColumnWidth(i, w)
        self._table.setStyleSheet(S.table())
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._context_menu)
        root.addWidget(self._table, 1)

    def _load(self):
        m = {"Все":None,"Ожидание":"pending","Выиграл":"won","Проиграл":"lost"}
        bets  = self.db.get_all_bets(status=m[self._filter.currentText()])
        stats = self.db.get_stats()
        roi   = stats["roi"]; profit = stats["total_profit"]

        self._c_total.set_value(str(stats["total"]))
        self._c_winrate.set_value(f"{stats['winrate']:.0f}%")
        self._c_roi.set_value(f"{'+' if roi>=0 else ''}{roi:.1f}%", S.success if roi>=0 else S.error)
        self._c_profit.set_value(f"{'+' if profit>=0 else ''}{profit:,} ₽", S.success if profit>=0 else S.error)

        icons  = {"won":"✅","lost":"❌","pending":"⏳"}
        colors = {"won":S.success,"lost":S.error,"pending":S.warning}
        self._table.setRowCount(len(bets))
        self._bets = bets
        for i, b in enumerate(bets):
            st = b["status"]; pr = b["profit"]
            self._table.setItem(i, 0, self._cell(b["date"], S.muted))
            self._table.setItem(i, 1, self._cell(b["match"]))
            self._table.setItem(i, 2, self._cell(b["forecast"], "#E2E8F0"))
            self._table.setItem(i, 3, self._cell(f"{b['odds']:.2f}", S.info))
            self._table.setItem(i, 4, self._cell(f"{b['stake']:,} ₽"))
            self._table.setItem(i, 5, self._cell(icons.get(st,"?"), colors.get(st,"#fff")))
            self._table.setItem(i, 6, self._cell(f"{'+' if pr>=0 else ''}{pr:,} ₽",
                                                  S.success if pr>0 else (S.error if pr<0 else S.muted)))
            self._table.setRowHeight(i, 48)

    def _context_menu(self, pos):
        row = self._table.rowAt(pos.y())
        if row < 0 or row >= len(self._bets): return
        bet  = self._bets[row]
        menu = QMenu(self)
        menu.setStyleSheet("QMenu{background:#1F2937;color:#E2E8F0;border:1px solid #374151;border-radius:6px;}"
                           "QMenu::item:selected{background:rgba(0,200,150,0.15);}")
        for status, label in [("won","✅ Выиграл"),("lost","❌ Проиграл"),("pending","⏳ Ожидание")]:
            if bet["status"] != status:
                act = QAction(label, self)
                act.triggered.connect(lambda _, s=status, bid=bet["id"]: (self.db.manual_update_status(bid,s), self._load()))
                menu.addAction(act)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    @staticmethod
    def _cell(text, color="#9CA3AF"):
        item = QTableWidgetItem(text)
        item.setForeground(QColor(color))
        return item
