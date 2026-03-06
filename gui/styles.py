"""
Design system v3.0 — PyQt6, Inter/JetBrains Mono, dark theme
"""


class S:
    # Palette
    bg        = "#0B0F1A"
    bg_card   = "#111827"
    bg_hover  = "#1F2937"
    border    = "#1F2937"
    border2   = "#374151"
    success   = "#00C896"
    warning   = "#FFD600"
    error     = "#FF6B6B"
    info      = "#4A9EFF"
    text      = "#E2E8F0"
    muted     = "#9CA3AF"
    dim       = "#6B7280"
    mono      = "JetBrains Mono, Consolas, Courier New, monospace"

    @staticmethod
    def card(radius: int = 8) -> str:
        return f"""
            background: #111827;
            border: 1px solid #1F2937;
            border-radius: {radius}px;
        """

    @staticmethod
    def btn_primary(color: str = "#00C896", radius: int = 6) -> str:
        return f"""
            QPushButton {{
                background: {color}22;
                border: 1px solid {color}88;
                color: {color};
                font-size: 12px;
                font-weight: 600;
                letter-spacing: 1px;
                border-radius: {radius}px;
                padding: 10px 24px;
            }}
            QPushButton:hover {{
                background: {color}44;
                border-color: {color};
            }}
            QPushButton:pressed {{
                background: {color}66;
            }}
            QPushButton:disabled {{
                opacity: 0.4;
            }}
        """

    @staticmethod
    def btn_solid(color: str = "#00C896", radius: int = 6) -> str:
        return f"""
            QPushButton {{
                background: {color};
                border: none;
                color: #0B0F1A;
                font-size: 12px;
                font-weight: 700;
                border-radius: {radius}px;
                padding: 10px 24px;
            }}
            QPushButton:hover {{
                background: {color}dd;
            }}
            QPushButton:pressed {{
                background: {color}bb;
            }}
        """

    @staticmethod
    def btn_ghost(radius: int = 6) -> str:
        return f"""
            QPushButton {{
                background: transparent;
                border: 1px solid #374151;
                color: #9CA3AF;
                font-size: 11px;
                border-radius: {radius}px;
                padding: 8px 18px;
            }}
            QPushButton:hover {{
                border-color: #6B7280;
                color: #E2E8F0;
                background: #1F2937;
            }}
        """

    @staticmethod
    def table() -> str:
        return """
            QTableWidget {
                background: transparent;
                border: none;
                color: #E2E8F0;
                font-size: 12px;
                gridline-color: transparent;
                selection-background-color: rgba(0,200,150,0.08);
            }
            QTableWidget::item {
                padding: 14px 12px;
                border-bottom: 1px solid #1F2937;
            }
            QTableWidget::item:selected { color: #E2E8F0; }
            QHeaderView::section {
                background: #111827;
                color: #6B7280;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1.5px;
                padding: 10px 12px;
                border: none;
                border-bottom: 1px solid #1F2937;
            }
        """

    @staticmethod
    def input() -> str:
        return """
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #0B0F1A;
                border: 1px solid #374151;
                color: #E2E8F0;
                font-size: 12px;
                padding: 8px 12px;
                border-radius: 6px;
            }
            QLineEdit:focus, QComboBox:focus { border-color: #00C896; }
            QComboBox::drop-down { border: none; padding-right: 8px; }
            QComboBox QAbstractItemView {
                background: #1F2937; color: #E2E8F0;
                border: 1px solid #374151; border-radius: 4px;
                selection-background-color: rgba(0,200,150,0.15);
            }
        """

    @staticmethod
    def progress_bar(color: str = "#00C896") -> str:
        return f"""
            QProgressBar {{
                background: #1F2937; border-radius: 3px; border: none; height: 6px;
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {color}, stop:1 {color}88);
                border-radius: 3px;
            }}
        """

    @staticmethod
    def tag(color: str = "#00C896") -> str:
        return f"""
            color: {color};
            background: {color}22;
            border: 1px solid {color}44;
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: 600;
        """

    @staticmethod
    def scroll_area() -> str:
        return "QScrollArea { border: none; background: transparent; }"

    @staticmethod
    def checkbox() -> str:
        return """
            QCheckBox { color: #D1D5DB; font-size: 12px; spacing: 8px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px;
                border: 1px solid #374151; background: #111827; }
            QCheckBox::indicator:checked { background: #00C896; border-color: #00C896; }
        """

    @staticmethod
    def radio() -> str:
        return """
            QRadioButton { color: #D1D5DB; font-size: 12px; spacing: 8px; }
            QRadioButton::indicator { width: 16px; height: 16px; border-radius: 8px;
                border: 2px solid #374151; background: #111827; }
            QRadioButton::indicator:checked { background: #00C896; border-color: #00C896; }
        """

    @staticmethod
    def tab_widget() -> str:
        return """
            QTabWidget::pane { border: none; background: transparent; }
            QTabBar::tab {
                background: transparent; color: #6B7280;
                font-size: 11px; font-weight: 600; letter-spacing: 1px;
                padding: 12px 24px; border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected { color: #00C896; border-bottom: 2px solid #00C896; }
            QTabBar::tab:hover { color: #E2E8F0; }
        """
