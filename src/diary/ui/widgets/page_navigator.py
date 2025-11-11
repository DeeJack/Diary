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

    go_to_first_requested: pyqtSignal = pyqtSignal()
    go_to_last_requested: pyqtSignal = pyqtSignal()
    open_navigation: pyqtSignal = pyqtSignal()
    open_settings: pyqtSignal = pyqtSignal()
    go_to_notebook_selector: pyqtSignal = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__("Navigation", parent)
        self.setMovable(False)
        self.setAutoFillBackground(False)
        self.setStyleSheet("background-color: #4b4d51")
        self.setStyleSheet("color: white")

        # Back to notebook selector
        self.back_btn: QPushButton = QPushButton()
        self.back_btn.setText("📚 Notebooks")
        self.back_btn.setFont(QFont("Times New Roman", 12))
        # self.back_btn.setStyleSheet("""
        #     QPushButton {
        #         background-color: #495057;
        #         border: 1px solid #6c757d;
        #         border-radius: 4px;
        #         padding: 6px 12px;
        #         color: #f8f9fa;
        #     }
        #     QPushButton:hover {
        #         background-color: #6c757d;
        #     }
        #     QPushButton:pressed {
        #         background-color: #5a6268;
        #     }
        # """)
        _ = self.back_btn.clicked.connect(self.go_to_notebook_selector.emit)

        # Go to first
        self.first_btn: QPushButton = QPushButton()
        self.first_btn.setText("Toggle navigation")
        self.first_btn.setFont(QFont("Times New Roman", 12))
        # self.first_btn.setFixedWidth(30)
        _ = self.first_btn.clicked.connect(self.open_navigation.emit)

        # Go to Last
        self.last_btn: QPushButton = QPushButton()
        self.last_btn.setText("Toggle settings")
        self.last_btn.setFont(QFont("Times New Roman", 12))
        # self.last_btn.setFixedWidth(30)
        _ = self.last_btn.clicked.connect(self.open_settings.emit)

        # Current page display
        self.page_label: QLabel = QLabel("Page 1 / ?")
        self.page_label.setStyleSheet("font-weight: bold; ")

        spacer_left = QWidget()
        spacer_left.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        spacer_right = QWidget()
        spacer_right.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        _ = self.addWidget(self.back_btn)
        _ = self.addWidget(self.first_btn)
        _ = self.addWidget(spacer_left)
        _ = self.addWidget(self.page_label)
        _ = self.addWidget(spacer_right)
        _ = self.addWidget(self.last_btn)

    @pyqtSlot(int, int)
    def update_page_display(self, current_page: int, total_pages: int):
        """PyQtSlot to update the page display"""
        self.page_label.setText(f"Page {current_page + 1} / {total_pages}")

        # Disable buttons when they are not needed
        # self.first_btn.setEnabled(current_page > 0)
        # self.last_btn.setEnabled(current_page < total_pages - 1)
        # if total_pages == 0:
        #     self.first_btn.setEnabled(False)
        #     self.last_btn.setEnabled(False)

    def set_back_button_visible(self, visible: bool):
        """Show or hide the back to notebook selector button"""
        self.back_btn.setVisible(visible)
