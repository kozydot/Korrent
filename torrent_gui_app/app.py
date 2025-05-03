import sys
import os # Added for path manipulation
import threading
import webbrowser
import pyperclip
import py1337x
from py1337x.types import category as py1337x_category, sort as py1337x_sort # lib type constants

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QStatusBar, QMessageBox, QListWidgetItem,
    QSizePolicy, QComboBox, QTableWidget, QTableWidgetItem, # table stuff
    QAbstractItemView, QHeaderView # table options
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QThread
from PyQt6.QtGui import QIcon # import qicon for setting window icon

# --- worker signals ---
# helps threads talk to the main gui safely
class WorkerSignals(QObject):
    search_finished = pyqtSignal(list)
    details_finished = pyqtSignal(object) # details obj or none if error
    error = pyqtSignal(str, str) # title, msg
    status_update = pyqtSignal(str)

# --- search worker thread ---
class SearchWorker(QThread):
    def __init__(self, query, category=None, sort_by=None, order='desc'): # needs search params
        super().__init__()
        self.query = query
        self.category = category # save params
        self.sort_by = sort_by
        self.order = order
        self.signals = WorkerSignals()

    def run(self):
        try:
            # build a string showing search params for status bar
            search_params = f"'{self.query}'"
            if self.category: search_params += f", Cat: {self.category}"
            if self.sort_by: search_params += f", Sort: {self.sort_by} ({self.order})"
            self.signals.status_update.emit(f"Searching for {search_params}...")

            torrents = py1337x.Py1337x()
            # actually run the search with the params
            results = torrents.search(
                query=self.query,
                category=self.category,
                sort_by=self.sort_by,
                order=self.order
            )
            # get items list, or empty list if no results
            items = results.items if results and results.items else []
            self.signals.search_finished.emit(items) # send results back
            # update status bar based on results
            if not items:
                 self.signals.status_update.emit("No results found.")
            else:
                 self.signals.status_update.emit(f"Found {len(items)} results.")
        except Exception as e:
            # oops, send error back
            self.signals.error.emit("Search Error", f"An error occurred during search:\n{e}")
            self.signals.status_update.emit(f"Search error: {e}")

# --- details worker thread ---
class DetailsWorker(QThread):
    def __init__(self, torrent_id):
        super().__init__()
        self.torrent_id = torrent_id
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.status_update.emit(f"Fetching details for torrent ID: {self.torrent_id}...")
            torrents = py1337x.Py1337x()
            info = torrents.info(torrent_id=self.torrent_id) # get details
            self.signals.details_finished.emit(info) # send details back
            self.signals.status_update.emit("Details loaded.")
        except Exception as e:
            # oops, send error back
            self.signals.error.emit("Details Error", f"Error fetching details:\n{e}")
            self.signals.details_finished.emit(None) # signal done even if error
            self.signals.status_update.emit(f"Details error: {e}")


# --- main application window ---
class TorrentApp(QWidget):
    def __init__(self):
        super().__init__()
        self.current_torrent_info = None # store selected torrent info
        self.search_worker = None # keep track of worker threads
        self.details_worker = None
        self.initUI()

    # --- UI Initialization ---
    def initUI(self):
        """Initializes the main UI components and layout."""
        self._setup_layouts()
        self._create_search_widgets()
        self._create_options_widgets()
        self._create_results_table()
        self._create_details_area()
        self._create_action_buttons()
        self._create_status_bar()
        self._assemble_main_layout()
        self._set_window_properties()
        self._load_stylesheet()
        self.show()

    def _setup_layouts(self):
        """Creates the main layout containers."""
        self.main_layout = QVBoxLayout(self)
        self.top_layout = QHBoxLayout()
        self.options_layout = QHBoxLayout()
        self.middle_layout = QHBoxLayout()
        self.bottom_layout = QHBoxLayout()

    def _create_search_widgets(self):
        """Creates the search input and button."""
        search_label = QLabel("Search:")
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Enter search query...")
        self.search_entry.returnPressed.connect(self.start_search)
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.start_search)

        self.top_layout.addWidget(search_label)
        self.top_layout.addWidget(self.search_entry)
        self.top_layout.addWidget(search_button)

    def _create_options_widgets(self):
        """Creates the category, sort, and order dropdowns."""
        category_label = QLabel("Category:")
        self.category_combo = QComboBox()
        self.category_combo.addItem("Any", None)
        for cat_name, cat_value in vars(py1337x_category).items():
            if not cat_name.startswith('_') and isinstance(cat_value, str):
                self.category_combo.addItem(cat_name.replace('_', ' ').title(), cat_value)

        sort_label = QLabel("Sort By:")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Default", None)
        self.sort_combo.addItem("Time", py1337x_sort.TIME)
        self.sort_combo.addItem("Size", py1337x_sort.SIZE)
        self.sort_combo.addItem("Seeders", py1337x_sort.SEEDERS)
        self.sort_combo.addItem("Leechers", py1337x_sort.LEECHERS)

        order_label = QLabel("Order:")
        self.order_combo = QComboBox()
        self.order_combo.addItem("Desc", "desc")
        self.order_combo.addItem("Asc", "asc")

        self.options_layout.addWidget(category_label)
        self.options_layout.addWidget(self.category_combo)
        self.options_layout.addSpacing(15)
        self.options_layout.addWidget(sort_label)
        self.options_layout.addWidget(self.sort_combo)
        self.options_layout.addSpacing(15)
        self.options_layout.addWidget(order_label)
        self.options_layout.addWidget(self.order_combo)
        self.options_layout.addStretch(1)

    def _create_results_table(self):
        """Creates and configures the results table."""
        self.results_group_layout = QVBoxLayout()
        results_label = QLabel("Results:")
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(2)
        self.results_table.setHorizontalHeaderLabels(["Name", "ID"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.itemSelectionChanged.connect(self.start_display_details)
        self.results_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results_table.setColumnHidden(1, True)

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.results_group_layout.addWidget(results_label)
        self.results_group_layout.addWidget(self.results_table)

    def _create_details_area(self):
        """Creates the details text area."""
        self.details_group_layout = QVBoxLayout()
        details_label = QLabel("Details:")
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)

        self.details_group_layout.addWidget(details_label)
        self.details_group_layout.addWidget(self.details_text)

    def _create_action_buttons(self):
        """Creates the copy magnet and download buttons."""
        self.copy_magnet_button = QPushButton("Copy Magnet Link")
        self.copy_magnet_button.setEnabled(False)
        self.copy_magnet_button.clicked.connect(self.copy_magnet)

        self.download_button = QPushButton("Download (Magnet)")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_torrent_via_magnet)

        self.bottom_layout.addWidget(self.copy_magnet_button)
        self.bottom_layout.addWidget(self.download_button)
        self.bottom_layout.addStretch(1)

    def _create_status_bar(self):
        """Creates the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Enter search query and press Search.")

    def _assemble_main_layout(self):
        """Adds all sub-layouts and widgets to the main layout."""
        self.middle_layout.addLayout(self.results_group_layout, 1)
        self.middle_layout.addLayout(self.details_group_layout, 2)

        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addLayout(self.options_layout)
        self.main_layout.addLayout(self.middle_layout)
        self.main_layout.addLayout(self.bottom_layout)
        self.main_layout.addWidget(self.status_bar)
        self.setLayout(self.main_layout)

    def _set_window_properties(self):
        """Sets window title, geometry, and icon."""
        self.setWindowTitle('Korrent1337x')
        self.setGeometry(100, 100, 850, 650)

        # Construct path relative to this script file
        script_dir = os.path.dirname(__file__)
        icon_filename = '20250501_0135_Yellow K Symbol_remix_01jt49z4whfamvprer8vckc5mw.png'
        # Go one level up from script_dir (torrent_gui_app) to the project root
        icon_path = os.path.join(script_dir, '..', icon_filename)

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Icon file not found at {icon_path}") # Add warning

    def _load_stylesheet(self):
        """Loads the stylesheet from style.qss."""
        script_dir = os.path.dirname(__file__)
        stylesheet_path = os.path.join(script_dir, 'style.qss')
        try:
            with open(stylesheet_path, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Warning: Stylesheet file not found at {stylesheet_path}")
        except Exception as e:
            print(f"Error loading stylesheet: {e}")


    # --- Helper Methods ---
    def _set_action_buttons_enabled(self, enabled: bool):
        """Enables or disables the copy and download buttons."""
        self.copy_magnet_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)

    def _stop_worker(self, worker: QThread):
        """Safely stops a running QThread worker."""
        if worker and worker.isRunning():
            worker.quit()
            worker.wait() # Wait for thread to finish cleanly

    # --- Slots (Event Handlers) ---
    def start_search(self):
        query = self.search_entry.text().strip()
        if not query:
            self.show_error("Input Error", "Please enter a search query.")
            return

        self.results_table.setRowCount(0)
        self.details_text.clear()
        self._set_action_buttons_enabled(False) # Use helper
        self.current_torrent_info = None

        # Stop previous search worker
        self._stop_worker(self.search_worker) # Use helper

        # Get selected options from dropdowns
        selected_category = self.category_combo.currentData()
        selected_sort = self.sort_combo.currentData()
        selected_order = self.order_combo.currentData()

        # start search worker thread w/ options
        self.search_worker = SearchWorker(
            query=query,
            category=selected_category,
            sort_by=selected_sort,
            order=selected_order
        )
        # connect signals from worker to slots in this class
        self.search_worker.signals.search_finished.connect(self.update_search_results)
        self.search_worker.signals.error.connect(self.show_error)
        self.search_worker.signals.status_update.connect(self.update_status)
        self.search_worker.start() # go!

    def update_search_results(self, items):
        self.results_table.setRowCount(0) # clear table first
        if not items:
            # maybe show msg in table? nah, status bar is fine
            self.update_status("No results found.")
            return

        self.results_table.setRowCount(len(items)) # make enough rows

        # fill the table
        for row, item in enumerate(items):
            name = getattr(item, 'name', 'N/A')
            torrent_id = getattr(item, 'torrent_id', None)

            # make table cells (items)
            name_item = QTableWidgetItem(name)
            name_item.setToolTip(name) # show full name on hover
            id_item = QTableWidgetItem(torrent_id) # store id in hidden cell

            # put cells in row
            self.results_table.setItem(row, 0, name_item)
            self.results_table.setItem(row, 1, id_item) # hidden id cell

        # resize cols? maybe not needed with stretch

    def start_display_details(self):
        selected_row = self.results_table.currentRow() # find selected row index
        if selected_row < 0: # nothing selected
            return

        # get the hidden id item from the selected row
        id_item = self.results_table.item(selected_row, 1) # id is col 1 now
        if not id_item:
             self.show_error("Error", "Could not retrieve torrent ID from selected row.")
             return

        torrent_id = id_item.text() # get id string

        # Check if id is valid before proceeding
        if not torrent_id: # Simplified check
            self.details_text.setHtml("<i>No details available.</i>")
            self._set_action_buttons_enabled(False) # Use helper
            self.current_torrent_info = None
            return

        # Show loading message & disable buttons
        self.details_text.setHtml("<i>Loading details...</i>")
        self._set_action_buttons_enabled(False) # Use helper
        self.current_torrent_info = None

        # Stop previous details worker
        self._stop_worker(self.details_worker) # Use helper

        # Start details worker thread
        self.details_worker = DetailsWorker(torrent_id)
        self.details_worker.signals.details_finished.connect(self.update_details_display)
        self.details_worker.signals.error.connect(self.show_error)
        self.details_worker.signals.status_update.connect(self.update_status)
        self.details_worker.start() # go!

    def update_details_display(self, info):
        self.current_torrent_info = info # store the fetched info
        if info is None:
            self.details_text.setHtml("<b>Error fetching details.</b>")
            self._set_action_buttons_enabled(False) # Use helper
            return

        # Use getattr for safety, format with html
        details_html = f"""
            <p><b>Name:</b> {getattr(info, 'name', 'N/A')}</p>
            <p><b>Category:</b> {getattr(info, 'category', 'N/A')}&nbsp;&nbsp;&nbsp;
               <b>Type:</b> {getattr(info, 'type', 'N/A')}&nbsp;&nbsp;&nbsp;
               <b>Language:</b> {getattr(info, 'language', 'N/A')}</p>
            <p><b>Size:</b> {getattr(info, 'size', 'N/A')}&nbsp;&nbsp;&nbsp;
               <b>Uploaded By:</b> {getattr(info, 'uploader', 'N/A')}</p>
            <p><b>Downloads:</b> {getattr(info, 'downloads', 'N/A')}&nbsp;&nbsp;&nbsp;
               <b>Last Checked:</b> {getattr(info, 'last_checked', 'N/A')}&nbsp;&nbsp;&nbsp;
               <b>Uploaded On:</b> {getattr(info, 'upload_date', 'N/A')}</p>
            <p><b>Seeders:</b> {getattr(info, 'seeders', 'N/A')}&nbsp;&nbsp;&nbsp;
               <b>Leechers:</b> {getattr(info, 'leechers', 'N/A')}</p>
            <hr>
            <p><b>Magnet Link:</b><br><code style='font-size: 9pt; word-wrap: break-word;'>{getattr(info, 'magnet_link', 'N/A')}</code></p>
            <p><b>Infohash:</b> {getattr(info, 'infohash', 'N/A')}</p>
            <p><b>Torrent Link:</b> {getattr(info, 'torrent_link', 'N/A')}</p>
        """
        self.details_text.setHtml(details_html) # display html

        # enable buttons only if magnet link exists
        has_magnet = bool(getattr(info, 'magnet_link', None))
        self._set_action_buttons_enabled(has_magnet) # Use helper


    def copy_magnet(self):
        if self.current_torrent_info:
            magnet = getattr(self.current_torrent_info, 'magnet_link', None)
            if magnet:
                try:
                    pyperclip.copy(magnet) # copy to clipboard
                    self.update_status("Magnet link copied to clipboard!")
                except pyperclip.PyperclipException:
                     # specific error for clipboard libs
                     self.show_error("Clipboard Error", "Could not copy to clipboard. Install 'xclip' or 'xsel' on Linux, or check permissions.")
                except Exception as e:
                    # general error
                    self.show_error("Error", f"An unexpected error occurred during copy: {e}")
            else:
                self.show_error("Copy Error", "No magnet link available in details.")
        else:
             self.show_error("Copy Error", "No torrent details loaded.")


    def download_torrent_via_magnet(self): # func name changed earlier
         if self.current_torrent_info:
            magnet_link = getattr(self.current_torrent_info, 'magnet_link', None) # get magnet
            if magnet_link:
                try:
                    # open magnet link (should start torrent client)
                    webbrowser.open(magnet_link)
                    self.update_status("Opening magnet link in default torrent client...")
                except Exception as e:
                    self.show_error("Error Opening Magnet Link", f"Could not open magnet link:\n{e}")
                    self.update_status("Failed to open magnet link.")
            else:
                self.show_error("Download Error", "No magnet link available in details.")
         else:
             self.show_error("Download Error", "No torrent details loaded.")

    def update_status(self, message):
        self.status_bar.showMessage(message)

    def show_error(self, title, message):
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event):
        """Stops worker threads before closing the application."""
        self._stop_worker(self.search_worker) # Use helper
        self._stop_worker(self.details_worker) # Use helper
        event.accept()


# --- Run Application ---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Stylesheet is now loaded within TorrentApp._load_stylesheet()
    ex = TorrentApp()
    sys.exit(app.exec())