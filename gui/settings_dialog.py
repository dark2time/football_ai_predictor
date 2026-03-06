"""Settings dialog v3 — PyQt6."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QLineEdit, QRadioButton, QButtonGroup,
    QCheckBox, QDoubleSpinBox, QFrame
)
from PyQt6.QtCore import Qt

from core.config import Config
from core.database import Database
from gui.styles import S
from gui.widgets import SectionLabel


class SettingsDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Настройки")
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet(f"background: #0B0F1A;")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Настройки").__class__("Настройки", styleSheet="color:#E2E8F0;font-size:20px;font-weight:700;"))
        title = QLabel("Настройки")
        title.setStyleSheet("color: #E2E8F0; font-size: 20px; font-weight: 700;")
        hdr.addWidget(title)
        hdr.addStretch()
        close = QPushButton("✕")
        close.setFixedSize(32,32); close.setStyleSheet(S.btn_ghost())
        close.clicked.connect(self.accept)
        hdr.addWidget(close)
        root.addLayout(hdr)

        tabs = QTabWidget()
        tabs.setStyleSheet(S.tab_widget())
        tabs.addTab(self._bank_tab(),   "Банк")
        tabs.addTab(self._plugin_tab(), "Плагины")
        tabs.addTab(self._filter_tab(), "Фильтры")
        root.addWidget(tabs)

        save = QPushButton("Сохранить")
        save.setFixedHeight(46)
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setStyleSheet(S.btn_solid())
        save.clicked.connect(self._save)
        root.addWidget(save)

    def _bank_tab(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(16,16,16,16); layout.setSpacing(16)
        br = self.db.get_bankroll()

        layout.addWidget(SectionLabel("Общий банк"))
        self._bank_in = QLineEdit(str(br["amount"]))
        self._bank_in.setFixedHeight(38); self._bank_in.setStyleSheet(S.input())
        layout.addWidget(self._bank_in)

        layout.addWidget(SectionLabel("Режим работы"))
        self._mode_grp = QButtonGroup()
        for mode, label, desc in [
            ("conservative","Консервативный","2% банка · Только угловые и карточки"),
            ("aggressive","Агрессивный","5% банка · Все рынки"),
        ]:
            row = QHBoxLayout()
            rb = QRadioButton(); rb.setChecked(br["mode"]==mode)
            rb.setProperty("mode_key", mode)
            rb.setStyleSheet(S.radio())
            self._mode_grp.addButton(rb)
            row.addWidget(rb)
            col = QVBoxLayout(); col.setSpacing(2)
            col.addWidget(QLabel(label, styleSheet=f"color:#E2E8F0;font-size:12px;font-weight:600;"))
            col.addWidget(QLabel(desc,  styleSheet=f"color:{S.muted};font-size:10px;"))
            row.addLayout(col); row.addStretch()
            layout.addLayout(row)
        layout.addStretch()
        return w

    def _plugin_tab(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(16,16,16,16); layout.setSpacing(10)
        layout.addWidget(SectionLabel("Включённые плагины"))
        self._plugin_chks = {}
        for key, cfg in Config.plugins().items():
            chk = QCheckBox(f"{cfg.get('emoji','')}  {cfg.get('name','')}")
            chk.setChecked(cfg.get("enabled", False))
            chk.setStyleSheet(S.checkbox())
            layout.addWidget(chk)
            self._plugin_chks[key] = chk
        layout.addStretch()
        return w

    def _filter_tab(self):
        w = QWidget(); layout = QVBoxLayout(w)
        layout.setContentsMargins(16,16,16,16); layout.setSpacing(14)
        fcfg = Config.get("filters") or {}

        layout.addWidget(SectionLabel("Value Bet"))
        row = QHBoxLayout()
        row.addWidget(QLabel("Минимальный Value (%):"))
        self._min_val = QDoubleSpinBox()
        self._min_val.setRange(1,30); self._min_val.setSingleStep(0.5)
        self._min_val.setValue(fcfg.get("min_value",0.08)*100)
        self._min_val.setStyleSheet(S.input()); self._min_val.setFixedHeight(36)
        row.addWidget(self._min_val); row.addStretch()
        layout.addLayout(row)

        self._auto_hide = QCheckBox("Скрывать матчи без Value автоматически")
        self._auto_hide.setChecked(fcfg.get("show_value_only",False))
        self._auto_hide.setStyleSheet(S.checkbox())
        layout.addWidget(self._auto_hide)

        layout.addWidget(SectionLabel("Красные флаги"))
        rf = fcfg.get("red_flags",{})
        self._rf = {}
        for key, lbl in [("derby","Дерби"),("after_european_match","После еврокубков"),("last_round","Последний тур")]:
            chk = QCheckBox(lbl); chk.setChecked(rf.get(key,True))
            chk.setStyleSheet(S.checkbox())
            layout.addWidget(chk); self._rf[key] = chk
        layout.addStretch()
        return w

    def _save(self):
        try:
            self.db.set_bankroll(int(self._bank_in.text()))
        except ValueError:
            pass
        for btn in self._mode_grp.buttons():
            if btn.isChecked():
                self.db.set_mode(btn.property("mode_key"))
                break
        cfg = Config.plugins()
        for k, chk in self._plugin_chks.items():
            if k in cfg: cfg[k]["enabled"] = chk.isChecked()
        Config.set(cfg, "plugins")
        fcfg = Config.get("filters") or {}
        fcfg["min_value"] = self._min_val.value()/100
        fcfg["show_value_only"] = self._auto_hide.isChecked()
        fcfg["red_flags"] = {k: c.isChecked() for k,c in self._rf.items()}
        Config.set(fcfg, "filters")
        self.accept()
