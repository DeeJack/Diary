"""The main window of the Diary application, containing all other Widgets"""

import logging
import sys
from pathlib import Path
from typing import cast, override

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QCloseEvent, QColor
from PyQt6.QtWidgets import (
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from diary.config import SETTINGS_FILE_PATH, settings
from diary.models import Notebook, NotebookDAO
from diary.ui.widgets.bottom_toolbar import BottomToolbar
from diary.ui.widgets.days_sidebar import DaysSidebar
from diary.ui.widgets.notebook_widget import NotebookWidget
from diary.ui.widgets.page_navigator import PageNavigatorToolbar
from diary.ui.widgets.save_manager import SaveManager
from diary.ui.widgets.settings_sidebar import SettingsSidebar
from diary.ui.widgets.tool_selector import Tool
from diary.utils.encryption import SecureBuffer, SecureEncryption
from src.diary.ui.notebook_selector import NotebookSelector


class MainWindow(QMainWindow):
    """Main window of the application, containing all other Widgets"""

    logger: logging.Logger = logging.getLogger("Main Window")

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Diary Application")
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("background-color: #2C2C2C;")
        self.showMaximized()

        self.logger.debug("Opening input dialog")
        password, ok = QInputDialog.getText(
            self,
            "Password Required",
            "Enter your encryption password:",
            QLineEdit.EchoMode.Password,
        )

        self.this_layout: QVBoxLayout
        self.navbar: PageNavigatorToolbar
        self.bottom_toolbar: BottomToolbar
        self.sidebar: DaysSidebar
        self.notebook_widget: NotebookWidget
        self.settings_sidebar: SettingsSidebar
        self.save_manager: SaveManager
        self.stored_selector: NotebookSelector | None = None

        self.logger.debug("Input dialog result: %s", ok)

        if ok and password:
            try:
                if settings.NOTEBOOK_FILE_PATH.exists():
                    self.logger.debug("Previous notebook exists, reading salt")

                    # Read salt from existing file
                    salt = SecureEncryption.read_salt_from_file(
                        settings.NOTEBOOK_FILE_PATH
                    )
                else:
                    self.logger.debug(
                        "Previous notebook does not exists, creating new salt"
                    )

                    # Generate new salt for new file
                    salt = SecureEncryption.generate_salt()

                self.logger.debug("Deriving new key from password and salt")
                key_buffer = SecureEncryption.derive_key(password, salt)

                # Clear password from memory immediately
                password_bytes = bytearray(password.encode("utf-8"))
                for i, _ in enumerate(password_bytes):
                    password_bytes[i] = 0
                password = ""

                status_bar = self.statusBar()
                if status_bar:
                    status_bar.showMessage("Password accepted. Key derived.", 5000)
                    status_bar.hide()

                self._load_widgets(key_buffer, salt)
            except ValueError as e:
                _ = QMessageBox.critical(self, "Error", str(e))
                _ = self.close()
                sys.exit(0)
        else:
            _ = self.close()
            sys.exit(0)

    def _load_widgets(self, key_buffer: SecureBuffer, salt: bytes):
        """Opens the Notebook with the given password"""
        main_widget = QWidget()
        self.this_layout = QVBoxLayout(main_widget)
        self.this_layout.setContentsMargins(0, 0, 0, 0)
        self.this_layout.setSpacing(0)
        self.navbar = PageNavigatorToolbar()
        self.bottom_toolbar = BottomToolbar()

        notebooks = NotebookDAO.loads(settings.NOTEBOOK_FILE_PATH, key_buffer)

        self.save_manager = SaveManager(
            notebooks, settings.NOTEBOOK_FILE_PATH, key_buffer, salt
        )

        self._show_notebook_selector(key_buffer, salt, notebooks)
        self.navbar.set_back_button_visible(False)

        self.setCentralWidget(main_widget)

    def _show_notebook_selector(
        self, key_buffer: SecureBuffer, salt: bytes, notebooks: list[Notebook]
    ):
        """Show the notebook selector widget"""
        self.setWindowTitle(settings.WINDOW_TITLE)
        if self.stored_selector:
            self.stored_selector.show()
            self.this_layout.addWidget(self.stored_selector)
            if hasattr(self, "notebook_widget"):
                self.this_layout.removeWidget(self.notebook_widget)
            return

        self.stored_selector = NotebookSelector(notebooks, self)

        def notebook_selected(notebook: Notebook):
            if self.stored_selector:
                self.stored_selector.hide()
                self.this_layout.removeWidget(self.stored_selector)
            self._open_notebook(key_buffer, salt, notebook, notebooks)

        _ = self.stored_selector.notebook_selected.connect(
            lambda notebook: notebook_selected(cast(Notebook, notebook))
        )
        self.this_layout.addWidget(self.stored_selector)

    def _go_back_to_notebook_selector(self):
        """Go back to the notebook selector from a notebook"""
        self.logger.debug("Going back to notebook selector")
        self.setWindowTitle(settings.WINDOW_TITLE)

        # Already on notebook selector
        if self.stored_selector and self.stored_selector.isVisible():
            self.logger.debug("Already on notebook selector, ignoring request")
            return

        # Save pending changes
        if hasattr(self, "save_manager"):
            self.save_manager.mark_dirty()
            self.save_manager.save()

        # Remove current notebook widgets
        if hasattr(self, "notebook_widget"):
            self.this_layout.removeWidget(self.notebook_widget)
            self.notebook_widget.hide()
        if hasattr(self, "toolbar"):
            self.this_layout.removeWidget(self.navbar)
            self.navbar.hide()
        if hasattr(self, "bottom_toolbar"):
            self.this_layout.removeWidget(self.bottom_toolbar)
            self.bottom_toolbar.hide()

        # Hide sidebars
        if hasattr(self, "sidebar"):
            self.sidebar.hide()
        if hasattr(self, "settings_sidebar"):
            self.settings_sidebar.hide()

        # Clear menu bar
        menu_bar = self.menuBar()
        if menu_bar:
            menu_bar.clear()

        # Show stored notebook selector
        if self.stored_selector:
            self.this_layout.addWidget(self.stored_selector)
            self.stored_selector.show()
            self.navbar.set_back_button_visible(False)
        else:
            self.logger.warning(
                "No stored selector available when going back to notebook selection"
            )

    def connect_signals(self, sidebar_toggle: QAction, settings_toggle: QAction):
        """Connects the Page Navigator signals"""
        _ = self.notebook_widget.current_page_changed.connect(
            self.navbar.update_page_display
        )

        _ = self.navbar.open_navigation.connect(sidebar_toggle.trigger)
        _ = self.navbar.open_settings.connect(settings_toggle.trigger)
        _ = self.navbar.go_to_notebook_selector.connect(
            self._go_back_to_notebook_selector
        )
        _ = self.navbar.save_requested.connect(self.save_manager.force_save)

        _ = self.bottom_toolbar.tool_changed.connect(
            lambda tool: self.notebook_widget.select_tool(cast(Tool, tool))
        )
        _ = self.bottom_toolbar.thickness_changed.connect(
            lambda t: self.notebook_widget.change_thickness(cast(float, t))
        )
        _ = self.bottom_toolbar.color_changed.connect(
            lambda c: self.notebook_widget.change_color(cast(QColor, c))
        )

        _ = self.settings_sidebar.pdf_imported.connect(self.pdf_imported)
        _ = self.settings_sidebar.pass_changed.connect(self.on_password_changed)

    @override
    def closeEvent(self, a0: QCloseEvent | None):
        """On app close event"""
        self.logger.debug("Close app event!")
        if a0 and hasattr(self, "save_manager"):
            settings.save_to_file(Path(SETTINGS_FILE_PATH))
            self.save_manager.force_save()
            a0.accept()

    def pdf_imported(self):
        """When the PDF has been imported, mark notebook as dirty and reload widget"""
        self.save_manager.force_save()
        self.notebook_widget.reload()

    def on_password_changed(self, new_data: tuple[SecureBuffer, bytes]):
        """When the password for the notebook has been changed, save new notebook"""
        self.save_manager.key_buffer = new_data[0]
        self.save_manager.salt = new_data[1]
        self.save_manager.force_save()
        self.logger.info("Password changed; saved new encrypted file")

    def _open_notebook(
        self,
        key_buffer: SecureBuffer,
        salt: bytes,
        notebook: Notebook,
        all_notebooks: list[Notebook],
    ):
        self.logger.debug("Loaded notebook, creating and opening NotebookWidget")
        self.notebook_widget = NotebookWidget(
            key_buffer, salt, notebook, all_notebooks, self.bottom_toolbar
        )
        self.notebook_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if not hasattr(self, "sidebar"):
            self.sidebar = DaysSidebar(self, self.notebook_widget)
            self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.sidebar)
            self.sidebar.hide()

        if not hasattr(self, "settings_sidebar"):
            self.settings_sidebar = SettingsSidebar(self, notebook)
            self.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self.settings_sidebar
            )
            self.settings_sidebar.hide()

        menu_bar = cast(QMenuBar, self.menuBar())
        view_menu = cast(QMenu, menu_bar.addMenu("&"))
        sidebar_action = self.sidebar.create_toggle_action()
        settings_action = self.settings_sidebar.create_toggle_action()
        view_menu.addAction(sidebar_action)
        view_menu.addAction(settings_action)

        self.connect_signals(sidebar_action, settings_action)
        self.notebook_widget.update_navbar()
        self.navbar.set_back_button_visible(True)

        self.this_layout.addWidget(self.navbar)
        self.this_layout.addWidget(self.notebook_widget)
        self.this_layout.addWidget(self.bottom_toolbar)
        self.navbar.show()
        self.bottom_toolbar.show()
        self.setWindowTitle(
            f"{settings.WINDOW_TITLE} - {notebook.metadata.get('name', 'Unnamed Notebook')}"
        )
