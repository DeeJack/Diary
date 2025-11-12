"""Top toolbar to go to first/last page, and show current page index"""

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolBar,
    QWidget,
)


class PageNavigatorToolbar(QToolBar):
    """Top navigation bar"""

    open_navigation: pyqtSignal = pyqtSignal()
    open_settings: pyqtSignal = pyqtSignal()
    go_to_notebook_selector: pyqtSignal = pyqtSignal()
    save_requested: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Navigation", parent)
        self.setMovable(False)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background-color: #4b4d51")
        self.setStyleSheet("color: white")

        # Go to first
        toggle_sidebar_btn = QPushButton()
        toggle_sidebar_btn.setText("Toggle navigation")
        toggle_sidebar_btn.setFont(QFont("Times New Roman", 12))
        _ = toggle_sidebar_btn.clicked.connect(self.open_navigation.emit)

        # Back to notebook selector
        self.notebook_selector_btn: QPushButton = QPushButton()
        self.notebook_selector_btn.setText("📚")
        self.notebook_selector_btn.setFixedWidth(40)
        self.notebook_selector_btn.setFont(QFont("Times New Roman", 12))
        _ = self.notebook_selector_btn.clicked.connect(
            self.go_to_notebook_selector.emit
        )

        # Current page display
        self.page_label: QLabel = QLabel("Page 1 / ?")
        self.page_label.setStyleSheet("font-weight: bold; ")

        save_btn = QPushButton()
        save_btn.setText("💾")
        save_btn.setFixedWidth(40)
        save_btn.setFont(QFont("Times New Roman", 12))
        _ = save_btn.clicked.connect(self.save_requested.emit)

        # Toggle settings sidebar
        toggle_settings_btn = QPushButton()
        toggle_settings_btn.setText("Toggle settings")
        toggle_settings_btn.setFont(QFont("Times New Roman", 12))
        _ = toggle_settings_btn.clicked.connect(self.open_settings.emit)

        spacer_left = QWidget()
        spacer_left.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        spacer_right = QWidget()
        spacer_right.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        _ = self.addWidget(toggle_sidebar_btn)
        _ = self.addWidget(self.notebook_selector_btn)
        _ = self.addWidget(spacer_left)
        _ = self.addWidget(self.page_label)
        _ = self.addWidget(spacer_right)
        _ = self.addWidget(save_btn)
        _ = self.addWidget(toggle_settings_btn)

    @pyqtSlot(int, int)
    def update_page_display(self, current_page: int, total_pages: int):
        """PyQtSlot to update the page display"""
        self.page_label.setText(f"Page {current_page + 1} / {total_pages}")

    def set_back_button_visible(self, visible: bool):
        """Show or hide the back to notebook selector button"""
        self.notebook_selector_btn.setVisible(visible)
