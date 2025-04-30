import sys
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

    def initUI(self):
        self.setWindowTitle('Korrent1337x') # new app name
        self.setGeometry(100, 100, 850, 650) # window size/pos

        # --- layouts ---
        main_layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        options_layout = QHBoxLayout() # sort/filter options here
        middle_layout = QHBoxLayout()
        bottom_layout = QHBoxLayout() # buttons here

        # --- top widgets (search) ---
        search_label = QLabel("Search:")
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Enter search query...")
        self.search_entry.returnPressed.connect(self.start_search) # allow enter key search
        search_button = QPushButton("Search")
        search_button.clicked.connect(self.start_search)

        top_layout.addWidget(search_label)
        top_layout.addWidget(self.search_entry)
        top_layout.addWidget(search_button)

        # --- options widgets (sort/filter) ---
        # category dropdown
        category_label = QLabel("Category:")
        self.category_combo = QComboBox()
        self.category_combo.addItem("Any", None) # default is no filter
        # fill dropdown from lib constants
        for cat_name, cat_value in vars(py1337x_category).items():
             if not cat_name.startswith('_') and isinstance(cat_value, str):
                 # make name readable, store actual value
                 self.category_combo.addItem(cat_name.replace('_', ' ').title(), cat_value)

        # sort by dropdown
        sort_label = QLabel("Sort By:")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Default", None)
        self.sort_combo.addItem("Time", py1337x_sort.TIME)
        self.sort_combo.addItem("Size", py1337x_sort.SIZE)
        self.sort_combo.addItem("Seeders", py1337x_sort.SEEDERS)
        self.sort_combo.addItem("Leechers", py1337x_sort.LEECHERS)

        # order dropdown
        order_label = QLabel("Order:")
        self.order_combo = QComboBox()
        self.order_combo.addItem("Desc", "desc")
        self.order_combo.addItem("Asc", "asc")

        options_layout.addWidget(category_label)
        options_layout.addWidget(self.category_combo)
        options_layout.addSpacing(15) # little gap
        options_layout.addWidget(sort_label)
        options_layout.addWidget(self.sort_combo)
        options_layout.addSpacing(15)
        options_layout.addWidget(order_label)
        options_layout.addWidget(self.order_combo)
        options_layout.addStretch(1) # push options left

        # --- middle widgets (results & details) ---
        results_group_layout = QVBoxLayout()
        details_group_layout = QVBoxLayout()

        results_label = QLabel("Results:")
        self.results_table = QTableWidget() # using a table now
        self.results_table.setColumnCount(2) # name, id (hidden)
        self.results_table.setHorizontalHeaderLabels(["Name", "ID"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows) # select whole row
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers) # cant edit table cells
        self.results_table.verticalHeader().setVisible(False) # hide row numbers
        self.results_table.itemSelectionChanged.connect(self.start_display_details) # run func on selection change
        self.results_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel) # smooth scroll!

        # hide the id column
        self.results_table.setColumnHidden(1, True) # id col is index 1

        # setup table header
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch) # name col takes available space

        results_group_layout.addWidget(results_label)
        results_group_layout.addWidget(self.results_table) # add table to its layout

        details_label = QLabel("Details:")
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)

        details_group_layout.addWidget(details_label)
        details_group_layout.addWidget(self.details_text)

        middle_layout.addLayout(results_group_layout, 1) # results take 1/3 space
        middle_layout.addLayout(details_group_layout, 2) # details take 2/3 space

        # --- bottom widgets (buttons) ---
        self.copy_magnet_button = QPushButton("Copy Magnet Link")
        self.copy_magnet_button.setEnabled(False)
        self.copy_magnet_button.clicked.connect(self.copy_magnet)

        self.download_button = QPushButton("Download (Magnet)") # button name changed earlier
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_torrent_via_magnet) # slot name changed earlier

        bottom_layout.addWidget(self.copy_magnet_button)
        bottom_layout.addWidget(self.download_button) # use correct button var
        bottom_layout.addStretch(1) # push buttons left

        # --- status bar ---
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Enter search query and press Search.")

        # --- assemble main layout ---
        main_layout.addLayout(top_layout)
        main_layout.addLayout(options_layout) # add options row
        main_layout.addLayout(middle_layout)
        main_layout.addLayout(bottom_layout)
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)
        self.show()

    # --- slots (event handlers) ---
    def start_search(self):
        query = self.search_entry.text().strip()
        if not query:
            self.show_error("Input Error", "Please enter a search query.")
            return

        self.results_table.setRowCount(0) # clear table
        self.details_text.clear()
        self.copy_magnet_button.setEnabled(False)
        self.download_button.setEnabled(False) # use correct button var
        self.current_torrent_info = None

        # stop previous search if still running
        if self.search_worker and self.search_worker.isRunning():
             self.search_worker.quit() # ask nicely
             self.search_worker.wait() # wait for it

        # get selected options from dropdowns
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

        # check if id is valid before proceeding
        if not torrent_id or torrent_id == "No results found.":
            self.details_text.setHtml("<i>No details available.</i>") # use html
            self.copy_magnet_button.setEnabled(False)
            self.download_button.setEnabled(False) # use correct button var
            self.current_torrent_info = None
            return

        # show loading message & disable buttons
        self.details_text.setHtml("<i>Loading details...</i>") # use html
        self.copy_magnet_button.setEnabled(False)
        self.download_button.setEnabled(False) # use correct button var
        self.current_torrent_info = None

        # stop previous details worker if running
        if self.details_worker and self.details_worker.isRunning():
             self.details_worker.quit()
             self.details_worker.wait()

        # start details worker thread
        self.details_worker = DetailsWorker(torrent_id)
        self.details_worker.signals.details_finished.connect(self.update_details_display)
        self.details_worker.signals.error.connect(self.show_error)
        self.details_worker.signals.status_update.connect(self.update_status)
        self.details_worker.start() # go!

    def update_details_display(self, info):
        self.current_torrent_info = info # store the fetched info
        if info is None: # means an error happened
            self.details_text.setHtml("<b>Error fetching details.</b>") # use html
            self.copy_magnet_button.setEnabled(False)
            self.download_button.setEnabled(False) # use correct button var
            return

        # use getattr for safety, format with html
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
        self.copy_magnet_button.setEnabled(has_magnet)
        self.download_button.setEnabled(has_magnet)


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
        # stop threads nicely when closing window
        if self.search_worker and self.search_worker.isRunning():
            self.search_worker.quit()
            self.search_worker.wait()
        if self.details_worker and self.details_worker.isRunning():
            self.details_worker.quit()
            self.details_worker.wait()
        event.accept() # allow window to close


# --- run application ---
if __name__ == '__main__':
    app = QApplication(sys.argv)

    # --- dark theme stylesheet ---
    dark_stylesheet = """
        QWidget {
            background-color: #2b2b2b;
            color: #f0f0f0;
            font-size: 10pt;
        }
        QLabel {
            color: #cccccc; /* lighter grey */
        }
        QLineEdit {
            background-color: #3c3f41;
            color: #f0f0f0;
            border: 1px solid #555555;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton {
            background-color: #555555;
            color: #f0f0f0;
            border: 1px solid #666666;
            padding: 5px 10px;
            border-radius: 3px;
            min-width: 80px; /* min button width */
        }
        QPushButton:hover {
            background-color: #666666;
            border: 1px solid #777777;
        }
        QPushButton:pressed {
            background-color: #444444;
        }
        QPushButton:disabled {
            background-color: #404040;
            color: #888888;
            border: 1px solid #555555;
        }
        /* QListWidget styles removed as it's no longer used */
        QTextEdit {
            background-color: #3c3f41;
            color: #f0f0f0;
            border: 1px solid #555555;
            border-radius: 3px;
        }
        QStatusBar {
            background-color: #2b2b2b;
            color: #cccccc;
        }
        QStatusBar::item {
            border: none; /* no status bar borders */
        }
        QMessageBox {
             background-color: #3c3f41; /* style msg boxes */
        }
        QMessageBox QLabel {
             color: #f0f0f0;
        }
        QMessageBox QPushButton {
             min-width: 60px; /* smaller msg box buttons */
        }
        QComboBox {
            background-color: #3c3f41;
            border: 1px solid #555555;
            padding: 3px 5px;
            border-radius: 3px;
            min-width: 6em; /* combo width */
        }
        QComboBox:hover {
            border: 1px solid #777777;
        }
        /* dropdown list style */
        QComboBox QAbstractItemView {
            background-color: #3c3f41;
            color: #f0f0f0;
            border: 1px solid #555555;
            selection-background-color: #0078d7; /* selection color */
            selection-color: #ffffff;
            outline: 0px; /* no focus outline */
        }
        /* dropdown arrow style */
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 15px;
            border-left-width: 1px;
            border-left-color: #555555;
            border-left-style: solid;
            border-top-right-radius: 3px;
            border-bottom-right-radius: 3px;
            background-color: #555555;
        }
        QComboBox::down-arrow {
            /* image: url(placeholder.png); */ /* needs real icon */
            width: 10px; /* arrow size */
            height: 10px;
        }
        QComboBox::down-arrow:on { /* shift arrow when open */
            top: 1px;
            left: 1px;
        }
        /* scrollbar style */
        QScrollBar:vertical {
            border: none;
            background: #2b2b2b; /* match bg */
            width: 10px; /* scrollbar width */
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #555555; /* handle color */
            min-height: 20px;
            border-radius: 5px; /* round corners */
        }
        QScrollBar::handle:vertical:hover {
            background: #666666; /* handle hover */
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            border: none;
            background: none;
            height: 0px; /* hide arrows */
            subcontrol-position: top;
            subcontrol-origin: margin;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none; /* track bg */
        }

        QScrollBar:horizontal {
            border: none;
            background: #2b2b2b;
            height: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:horizontal {
            background: #555555;
            min-width: 20px;
            border-radius: 5px;
        }
         QScrollBar::handle:horizontal:hover {
            background: #666666;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            border: none;
            background: none;
            width: 0px; /* hide arrows */
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
        /* table header style */
        QHeaderView::section {
           background-color: #3c3f41;
           color: #cccccc;
           padding: 4px;
           border: 1px solid #555555;
           border-bottom: none; /* avoid double border */
        }
        QTableWidget { /* table style */
           background-color: #3c3f41;
           border: 1px solid #555555;
           border-radius: 3px;
           gridline-color: #555555; /* grid line color */
        }
        QTableWidget::item {
            padding: 3px;
            color: #f0f0f0;
        }
        QTableWidget::item:selected {
            background-color: #0078d7;
            color: #ffffff;
        }

    """
    app.setStyleSheet(dark_stylesheet)

    ex = TorrentApp()
    sys.exit(app.exec())