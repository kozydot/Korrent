import sys
import os # for path stuff
import threading
import webbrowser
import pyperclip
import py1337x
import json
from typing import Optional
from py1337x.types import category as py1337x_category, sort as py1337x_sort # library type constants
from custom_1337x import Custom1337x, ALTERNATIVE_DOMAINS  # Import our custom module with domains
from widgets import SearchControls, DetailsArea, ResultsTab, FavoritesTab, ActionButtons

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QStatusBar, QMessageBox, QListWidgetItem,
    QSizePolicy, QComboBox, QTableWidget, QTableWidgetItem, # for the results table
    QAbstractItemView, QHeaderView, QCompleter, QTabWidget, QGroupBox, QFileDialog # table display options
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QThread, QStringListModel
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QPolygon, QFont # for the window icon

# --- worker signals ---
# helps the main thread communicate with the worker threads
class WorkerSignals(QObject):
    search_finished = pyqtSignal(list)
    details_finished = pyqtSignal(object) # details object, or none if there's an error
    error = pyqtSignal(str, str) # error title, message
    status_update = pyqtSignal(str)

# --- worker threads ---
class SearchWorker(QThread):
    """worker thread for running searches without freezing the gui."""
    def __init__(self, query, category=None, sort_by=None, order='desc', domain=None): # needs search parameters
        super().__init__()
        self.query = query
        self.category = category
        self.sort_by = sort_by
        self.order = order
        self.domain = domain
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.status_update.emit(f"Searching for '{self.query}'...")
            
            # Use our custom 1337x class with domain rotation
            custom_1337x = Custom1337x(base_url=self.domain or "")
            
            # get the search results from the custom class
            results = custom_1337x.search(self.query, category=self.category, sort_by=self.sort_by, order=self.order)
            
            # We are using our custom search method, which returns a list of torrent items
            # These are dictionaries, not objects
            items = results.items if results else []
            
            if not items:
                self.signals.status_update.emit(f"No results found for '{self.query}'.")
                self.signals.search_finished.emit([])
            else:
                self.signals.search_finished.emit(items)
                
        except Exception as e:
            self.signals.error.emit("Search Error", str(e))
            self.signals.search_finished.emit([])


class DetailsWorker(QThread):
    """worker thread for fetching torrent details without freezing the gui."""
    def __init__(self, torrent_id, domain=None):
        super().__init__()
        self.torrent_id = torrent_id
        self.domain = domain
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.status_update.emit(f"Fetching details for torrent ID: {self.torrent_id}...")
            
            # Use our custom 1337x class with domain rotation
            custom_1337x = Custom1337x(base_url=self.domain or "")
            
            # get the torrent details from the custom class
            details = custom_1337x.info(torrent_id=self.torrent_id)
            self.signals.details_finished.emit(details)
            
        except Exception as e:
            self.signals.error.emit("Details Error", str(e))
            self.signals.details_finished.emit(None)


# --- main application ---
class TorrentApp(QWidget):
    def __init__(self):
        super().__init__()
        
        # --- data ---
        self.search_history = self.load_search_history()
        self.favorites = self.load_favorites()
        self.current_torrent_info = None  # To store the latest fetched details
        self.search_worker = None # Search worker thread
        self.details_worker = None # Details worker thread
        
        # --- ui initialization ---
        self.initUI()

    # --- ui initialization ---\
    def initUI(self):
        """initializes the main ui components and layout."""
        self._setup_layouts()
        self._create_search_controls()
        self._create_tabs()
        self._create_details_area()
        self._create_action_buttons()
        self._create_status_bar()
        self._assemble_main_layout()
        self._set_window_properties()
        self._load_stylesheet()

        self.update_favorites_table() # initial load
        self.set_action_buttons_enabled(False) # start with action buttons disabled

    def _setup_layouts(self):
        """sets up the main layouts for the application."""
        self.main_layout = QVBoxLayout(self)
        self.top_layout = QVBoxLayout()
        self.middle_layout = QHBoxLayout()

    def _create_search_controls(self):
        """creates the search bar and filter controls."""
        self.search_controls = SearchControls(self.search_history)
        self.search_controls.search_button.clicked.connect(self.start_search)
        self.search_controls.search_entry.returnPressed.connect(self.start_search)
        
        clear_history_button = QPushButton("Clear History")
        clear_history_button.clicked.connect(self.clear_search_history)
        clear_history_button.setToolTip("Clear search history")
        self.search_controls.add_widget_to_search_layout(clear_history_button)

        self.top_layout.addWidget(self.search_controls)

    def _create_tabs(self):
        """Creates tab widget with search results and favorites tabs."""
        # Create tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        # Search results tab
        self.search_tab = ResultsTab()
        self.search_tab.results_table.itemSelectionChanged.connect(self.start_display_details)

        # Favorites tab
        self.favorites_tab = FavoritesTab()
        self.favorites_tab.favorites_table.itemSelectionChanged.connect(self.start_display_favorite_details)
        self.favorites_tab.add_favorite_button.clicked.connect(self.add_to_favorites)
        self.favorites_tab.remove_favorite_button.clicked.connect(self.remove_from_favorites)        # Add tabs to widget
        self.tab_widget.addTab(self.search_tab, "Search Results")
        self.tab_widget.addTab(self.favorites_tab, "Favorites")
        
    def _create_details_area(self):
        """Creates the torrent details display area."""
        self.details_area = DetailsArea()

    def _create_action_buttons(self):
        """Creates buttons for magnet link and download actions."""
        self.action_buttons = ActionButtons()
        self.action_buttons.copy_magnet_button.clicked.connect(self.copy_magnet)
        self.action_buttons.download_button.clicked.connect(self.download_torrent_via_magnet)
        self.action_buttons.add_favorite_button.clicked.connect(self.add_to_favorites)

        self.set_action_buttons_enabled(False) # disabled by default

    def _create_status_bar(self):
        """Creates the status bar."""
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        
    def _assemble_main_layout(self):
        """Assembles the main layout of the application."""
        left_pane_widget = QWidget()
        left_pane_layout = QVBoxLayout(left_pane_widget)
        left_pane_layout.setContentsMargins(0, 0, 0, 0)
        left_pane_layout.addWidget(self.details_area)
        left_pane_layout.addWidget(self.action_buttons)

        self.middle_layout.addWidget(left_pane_widget, 3)
        self.middle_layout.addWidget(self.tab_widget, 7)
        
        self.main_layout.addLayout(self.top_layout)
        self.main_layout.addLayout(self.middle_layout)
        self.main_layout.addWidget(self.status_bar)

    def _set_window_properties(self):
        """Sets window properties like title, icon, and size."""
        self.setWindowTitle("Korrent")
        
        # set window icon
        script_dir = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(script_dir, '..', '..', 'image', 'image.png')
        self.setWindowIcon(QIcon(icon_path))
        
        self.setGeometry(100, 100, 1200, 800)

    def _load_stylesheet(self):
        """Loads the application's stylesheet."""
        script_dir = os.path.dirname(os.path.realpath(__file__))
        stylesheet_path = os.path.join(script_dir, 'style.qss')
        try:
            with open(stylesheet_path, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Stylesheet not found.") # fallback to default styles
            
    # --- ui actions and slots ---
    def set_action_buttons_enabled(self, enabled: bool):
        """Enable or disable action buttons based on whether a torrent is selected."""
        self.action_buttons.set_buttons_enabled(enabled)

    def _stop_worker(self, worker: Optional[QThread]):
        """Safely stops a QThread worker if it is running."""
        if worker and worker.isRunning():
            worker.quit()
            worker.wait()

    def start_search(self):
        """initiates a torrent search."""
        self._stop_worker(self.search_worker) # stop any previous search
        
        params = self.search_controls.get_search_parameters()
        query = params['query']

        if not query:
            self.show_error("Empty Search", "Please enter a search query.")
            return

        self.update_search_history(query)
        self.search_tab.clear_results()
        self.details_area.clear_details()
        self.favorites_tab.add_favorite_button.setEnabled(False)
        self.set_action_buttons_enabled(False)
        
        # a new search worker is created with the search parameters
        self.search_worker = SearchWorker(
            query,
            category=params['category'],
            sort_by=params['sort_by'],
            order=params['order'],
            domain=params['domain']
        )
        self.search_worker.signals.search_finished.connect(self.update_search_results)
        self.search_worker.signals.error.connect(self.show_error)
        self.search_worker.signals.status_update.connect(self.update_status)
        self.search_worker.start()

    def update_search_results(self, items):
        """Populates the search results table with data from the search worker."""
        self.search_tab.populate_results(items)

        if not items:
            self.update_status("No results found.")
        else:
            self.update_status(f"Found {len(items)} results.")
        
    def start_display_details(self):
        """
        Initiates fetching and displaying details for the selected torrent.
        Triggered when a row in the results table is selected.
        """
        selected_items = self.search_tab.results_table.selectedItems()
        if not selected_items:
            self.current_torrent_info = None
            self.favorites_tab.add_favorite_button.setEnabled(False)
            self.set_action_buttons_enabled(False)
            return

        selected_row = selected_items[0].row()
        torrent_id_item = self.search_tab.results_table.item(selected_row, 5) # get ID from hidden column
        
        if not torrent_id_item:
            return

        torrent_id = torrent_id_item.text()
          # Get the domain used for the search
        params = self.search_controls.get_search_parameters()
        domain = params["domain"]

        self._stop_worker(self.details_worker) # stop any previous details worker
        self.details_worker = DetailsWorker(torrent_id, domain)
        self.details_worker.signals.details_finished.connect(self.update_details_display)
        self.details_worker.signals.error.connect(self.show_error)
        self.details_worker.signals.status_update.connect(self.update_status)
        self.details_worker.start()

    def update_details_display(self, info):
        """
        Updates the details view with information from the details worker.
        """
        self.current_torrent_info = info
        if info and info.magnet_link:
            # Check if this torrent is already a favorite
            is_favorite = any(fav['torrentId'] == info.torrent_id for fav in self.favorites if 'torrentId' in fav)
            self.favorites_tab.add_favorite_button.setText("In Favorites" if is_favorite else "Add to Favorites")
            self.favorites_tab.add_favorite_button.setEnabled(not is_favorite)
            
            # Update action buttons favorite button state
            self.action_buttons.add_favorite_button.setText("In Favorites" if is_favorite else "Add to Favorites")
            self.action_buttons.add_favorite_button.setEnabled(not is_favorite)

            self.set_action_buttons_enabled(True)
            
            # Format details with HTML for better presentation
            description_html = info.description.replace('\\n', '<br>') if info.description else "No description available."
            details_html = f"""
                <body style='font-family: sans-serif; font-size: 10pt;'>
                    <h3>{info.name}</h3>
                    <p>
                        <b>Category:</b> {info.category} &nbsp;&nbsp;&nbsp;
                        <b>Type:</b> {info.type} &nbsp;&nbsp;&nbsp;
                        <b>Language:</b> {info.language} &nbsp;&nbsp;&nbsp;
                        <b>Size:</b> {info.size}
                    </p>
                    <p>
                        <b>Seeders:</b> <span style='color: #4CAF50;'>{info.seeders}</span> &nbsp;&nbsp;&nbsp;
                        <b>Leechers:</b> <span style='color: #F44336;'>{info.leechers}</span> &nbsp;&nbsp;&nbsp;
                        <b>Downloads:</b> {info.downloads}
                    </p>
                    <p>
                        <b>Uploaded by:</b> {info.uploader} &nbsp;&nbsp;&nbsp;
                        <b>Date uploaded:</b> {info.date_uploaded} &nbsp;&nbsp;&nbsp;
                        <b>Last checked:</b> {info.last_checked}
                    </p>
                    <h4>Description</h4>
                    <div>{description_html}</div>
                </body>
            """
            self.details_area.update_details(details_html)
        else:
            self.details_area.clear_details()
            self.set_action_buttons_enabled(False)
            self.favorites_tab.add_favorite_button.setEnabled(False)

    def copy_magnet(self):
        """Copies the magnet link of the selected torrent to the clipboard."""
        if self.current_torrent_info and self.current_torrent_info.magnet_link:
            pyperclip.copy(self.current_torrent_info.magnet_link)
            self.update_status("Magnet link copied to clipboard.")
        else:
            self.show_error("Copy Error", "No magnet link available to copy.")

    def download_torrent_via_magnet(self):
        """Opens the magnet link in the default torrent client."""
        if self.current_torrent_info and self.current_torrent_info.magnet_link:
            webbrowser.open(self.current_torrent_info.magnet_link)
            self.update_status("Opening magnet link in default torrent client...")
        else:
            self.show_error("Download Error", "No magnet link available.")
            
    def update_status(self, message):
        """Updates the status bar with a message."""
        self.status_bar.showMessage(message)

    def show_error(self, title, message):
        """Shows an error message box."""
        QMessageBox.critical(self, title, message)

    def closeEvent(self, event):
        """Handle the window close event to stop running threads."""
        self._stop_worker(self.search_worker)
        self._stop_worker(self.details_worker)
        event.accept()

    def load_search_history(self):
        """Loads search history from a JSON file."""
        history_path = os.path.join(os.path.dirname(__file__), 'search_history.json')
        try:
            with open(history_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_search_history(self):
        """Saves search history to a JSON file."""
        history_path = os.path.join(os.path.dirname(__file__), 'search_history.json')
        try:
            with open(history_path, 'w') as f:
                json.dump(self.search_history, f, indent=4)
        except IOError:
            self.show_error("History Error", "Could not save search history.")

    def update_search_history(self, query):
        """Updates the search history with a new query."""
        if query not in self.search_history:
            self.search_history.insert(0, query)
            # a limit to the history size
            if len(self.search_history) > 50:
                self.search_history.pop()
            
            # Update completer model
            completer_model = QStringListModel(self.search_history)
            self.search_controls.search_completer.setModel(completer_model)

    def clear_search_history(self):
        """Clears the search history."""
        self.search_history = []
        completer_model = QStringListModel(self.search_history)
        self.search_controls.search_completer.setModel(completer_model)
        self.update_status("Search history cleared.")
        self.save_search_history()

    def load_favorites(self):
        """Loads favorites from a JSON file."""
        favorites_path = os.path.join(os.path.dirname(__file__), 'favorites.json')
        try:
            with open(favorites_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_favorites(self):
        """Saves favorites to a JSON file."""
        favorites_path = os.path.join(os.path.dirname(__file__), 'favorites.json')
        try:
            with open(favorites_path, 'w') as f:
                json.dump(self.favorites, f, indent=4)
        except IOError:
            self.show_error("Favorites Error", "Could not save favorites.")

    def update_favorites_table(self):
        """Repopulates the favorites table from the favorites list."""
        self.favorites_tab.populate_favorites(self.favorites)

    def add_to_favorites(self):
        """Adds the currently viewed torrent to the favorites list."""
        if self.current_torrent_info:
            is_favorite = any(fav['torrentId'] == self.current_torrent_info.torrent_id for fav in self.favorites if 'torrentId' in fav)
            if not is_favorite:
                # Add necessary info to favorites list
                self.favorites.append({
                    'torrentId': self.current_torrent_info.torrent_id,
                    'name': self.current_torrent_info.name,
                    'category': self.current_torrent_info.category,
                    'size': self.current_torrent_info.size,
                    'seeders': self.current_torrent_info.seeders,
                    'leechers': self.current_torrent_info.leechers,                    'domain': self.search_controls.get_search_parameters()['domain'] # save domain used
                })
                self.save_favorites()
                self.update_favorites_table()
                self.update_status(f"Added '{self.current_torrent_info.name}' to favorites.")
                
                # Update button state in both tabs and action buttons
                self.favorites_tab.add_favorite_button.setText("In Favorites")
                self.favorites_tab.add_favorite_button.setEnabled(False)
                self.action_buttons.add_favorite_button.setText("In Favorites")
                self.action_buttons.add_favorite_button.setEnabled(False)
            else:
                self.update_status("This torrent is already in your favorites.")

    def remove_from_favorites(self):
        """Removes the selected torrent from the favorites list."""
        selected_items = self.favorites_tab.favorites_table.selectedItems()
        if not selected_items:
            self.show_error("Remove Error", "Please select a favorite to remove.")
            return

        selected_row = selected_items[0].row()
        torrent_id_item = self.favorites_tab.favorites_table.item(selected_row, 5)

        if not torrent_id_item:
            self.show_error("Remove Error", "Could not identify selected favorite.")
            return
            
        torrent_id_to_remove = torrent_id_item.text()

        # Find and remove the favorite from the list
        self.favorites = [fav for fav in self.favorites if fav.get('torrentId') != torrent_id_to_remove]
        self.save_favorites()
        self.update_favorites_table()
        self.update_status("Favorite removed.")
        self.favorites_tab.remove_favorite_button.setEnabled(False)

    def on_tab_changed(self, index):
        """Handle tab changes to update UI state, e.g., enabling/disabling buttons."""
        # Prevent crash on startup if signal fires before UI is fully initialized
        if not hasattr(self, 'details_area'):
            return

        is_favorites_tab = self.tab_widget.tabText(index) == "Favorites"
        self.favorites_tab.remove_favorite_button.setEnabled(is_favorites_tab and bool(self.favorites_tab.favorites_table.selectedItems()))
        
        # When switching away from favorites, clear details if they are from a favorite
        # A simple way is to check the selection on the other table
        if not is_favorites_tab:
            if not self.search_tab.results_table.selectedItems():
                self.details_area.clear_details()
                self.favorites_tab.add_favorite_button.setEnabled(False)
                self.set_action_buttons_enabled(False)
        else: # on favs tab
             if not self.favorites_tab.favorites_table.selectedItems():
                self.details_area.clear_details()
                self.favorites_tab.add_favorite_button.setEnabled(False)
                self.set_action_buttons_enabled(False)


    def start_display_favorite_details(self):
        """Fetches and displays details for a selected favorite torrent."""
        selected_items = self.favorites_tab.favorites_table.selectedItems()
        if not selected_items:
            return

        selected_row = selected_items[0].row()
        torrent_id_item = self.favorites_tab.favorites_table.item(selected_row, 5)
        
        if not torrent_id_item:
            return

        torrent_id = torrent_id_item.text()
        domain = ""
        # Find the domain used for this favorite, if stored
        for fav in self.favorites:
            if fav.get('torrentId') == torrent_id:
                domain = fav.get('domain', "")
                break
        
        # When a favorite is selected, enable the remove button
        self.favorites_tab.remove_favorite_button.setEnabled(True)

        # Use the details worker to fetch fresh data
        self._stop_worker(self.details_worker)
        self.details_worker = DetailsWorker(torrent_id, domain)
        self.details_worker.signals.details_finished.connect(self.update_details_display)
        self.details_worker.signals.error.connect(self.show_error)
        self.details_worker.signals.status_update.connect(self.update_status)
        self.details_worker.start()

# --- application entry point ---
def main():
    app = QApplication(sys.argv)
    ex = TorrentApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()