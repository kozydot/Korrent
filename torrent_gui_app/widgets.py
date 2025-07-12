from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLineEdit, QPushButton,
    QLabel, QComboBox, QCompleter, QAbstractItemView, QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QTextEdit, QCheckBox
)
from PyQt6.QtCore import Qt, QStringListModel, pyqtSignal
from PyQt6.QtGui import QColor


class SearchControls(QWidget):
    def __init__(self, search_history, parent=None):
        super().__init__(parent)
        self.search_history = search_history
        self._init_widgets()
        self._init_layouts()

    def _init_widgets(self):
        # Search entry
        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Enter search query...")
        self.search_completer = QCompleter(self.search_history)
        self.search_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.search_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.search_entry.setCompleter(self.search_completer)
        
        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.setMinimumWidth(80)
        
        # Test connection button  
        self.test_connection_button = QPushButton("Test Connection")
        self.test_connection_button.setMinimumWidth(120)
        
        # Server status indicator
        self.server_status_label = QLabel("🔄 Starting server...")
        self.server_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        self.server_status_label.setToolTip("TorrentApi server status")
        
        # Category dropdown - matching TorrentApi categories
        self.category_combo = QComboBox()
        self.category_combo.addItem("Any", None)
        self.category_combo.addItem("Movies/TV", "Movies/TV")
        self.category_combo.addItem("Music", "Music")
        self.category_combo.addItem("Games", "Games")
        self.category_combo.addItem("Apps", "Apps")
        self.category_combo.addItem("Other", "Other")
        
        # Sort dropdown - matching TorrentApi sort options
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Default", None)
        self.sort_combo.addItem("Time", "time")
        self.sort_combo.addItem("Size", "size")
        self.sort_combo.addItem("Seeders", "seeders")
        self.sort_combo.addItem("Leechers", "leechers")
        
        # Order dropdown
        self.order_combo = QComboBox()
        self.order_combo.addItem("Desc", "desc")
        self.order_combo.addItem("Asc", "asc")
        
        # API URL input
        self.api_url_label = QLabel("API URL:")
        self.api_url_input = QLineEdit()
        self.api_url_input.setText("http://localhost:8000")
        self.api_url_input.setPlaceholderText("TorrentApi URL (e.g., http://localhost:8000)")
        
        # Provider selection - simple dropdown
        self.providers_label = QLabel("Providers:")
        self.providers_combo = QComboBox()
        self.providers_combo.addItem("All", ["PirateBay", "YTS", "BitSearch"])
        self.providers_combo.addItem("PirateBay", ["PirateBay"])
        self.providers_combo.addItem("YTS", ["YTS"])
        self.providers_combo.addItem("BitSearch", ["BitSearch"])
        self.providers_combo.addItem("PirateBay + YTS", ["PirateBay", "YTS"])
        self.providers_combo.addItem("PirateBay + BitSearch", ["PirateBay", "BitSearch"])
        self.providers_combo.setCurrentIndex(0)  # Default to "All"

    def _init_layouts(self):
        main_layout = QVBoxLayout(self)
        
        # Top row: Search bar and buttons
        self.search_layout = QHBoxLayout()
        self.search_layout.setSpacing(8)
        self.search_layout.addWidget(QLabel("Search:"))
        self.search_layout.addWidget(self.search_entry, 1)
        self.search_layout.addSpacing(10)  # Add space before buttons
        self.search_layout.addWidget(self.search_button)
        self.search_layout.addWidget(self.test_connection_button)
        
        # Bottom row: Options
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Category:"))
        options_layout.addWidget(self.category_combo)
        options_layout.addSpacing(15)
        options_layout.addWidget(QLabel("Sort By:"))
        options_layout.addWidget(self.sort_combo)
        options_layout.addSpacing(15)
        options_layout.addWidget(QLabel("Order:"))
        options_layout.addWidget(self.order_combo)
        options_layout.addSpacing(15)
        options_layout.addWidget(self.api_url_label)
        options_layout.addWidget(self.api_url_input)
        options_layout.addSpacing(15)
        options_layout.addWidget(self.providers_label)
        options_layout.addWidget(self.providers_combo)
        options_layout.addSpacing(10)  # Add spacing before server status
        options_layout.addWidget(self.server_status_label)  # Server status beside providers
        options_layout.addStretch(1)
        
        main_layout.addLayout(self.search_layout)
        main_layout.addSpacing(8)  # Add spacing between rows
        main_layout.addLayout(options_layout)

    def add_widget_to_search_layout(self, widget):
        self.search_layout.addSpacing(10)  # Add spacing before additional widgets
        self.search_layout.addWidget(widget)

    def update_server_status(self, status, message):
        """Update the server status indicator."""
        status_styles = {
            'starting': "color: #FF9800; font-weight: bold;",  # Orange
            'running': "color: #4CAF50; font-weight: bold;",   # Green
            'error': "color: #F44336; font-weight: bold;",     # Red
            'stopped': "color: #9E9E9E; font-weight: bold;"   # Gray
        }
        
        status_icons = {
            'starting': "🔄",
            'running': "✅", 
            'error': "❌",
            'stopped': "⏹️"
        }
        
        icon = status_icons.get(status, "❓")
        style = status_styles.get(status, "color: #9E9E9E; font-weight: bold;")
        
        self.server_status_label.setText(f"{icon} {message}")
        self.server_status_label.setStyleSheet(style)
        self.server_status_label.setToolTip(f"TorrentApi server status: {message}")

    def get_search_parameters(self):
        return {
            "query": self.search_entry.text(),
            "category": self.category_combo.currentData(),
            "sort_by": self.sort_combo.currentData(),
            "order": self.order_combo.currentData(),
            "api_url": self.api_url_input.text() or "http://localhost:8000",
            "providers": self.providers_combo.currentData()
        }

class ResultsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_widgets()
        self._init_layouts()

    def _init_widgets(self):
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(7)
        self.results_table.setHorizontalHeaderLabels(["Name", "Size", "Seeders", "Leechers", "Date", "Provider", "ID"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.results_table.setColumnHidden(6, True)  # Hide ID column
        self.results_table.setWordWrap(True)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setDefaultSectionSize(50)
        self.results_table.setColumnWidth(0, 350)
        self.results_table.setColumnWidth(1, 80)
        self.results_table.setColumnWidth(2, 80)
        self.results_table.setColumnWidth(3, 80)
        self.results_table.setColumnWidth(4, 120)
        self.results_table.setColumnWidth(5, 100)

        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)

    def _init_layouts(self):
        layout = QVBoxLayout(self)
        label = QLabel("Search Results:")
        label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(label)
        layout.addWidget(self.results_table)

    def clear_results(self):
        self.results_table.clearContents()
        self.results_table.setRowCount(0)

    def populate_results(self, items):
        self.clear_results()
        self.results_table.setRowCount(len(items))

        for row, item in enumerate(items):
            # Handle both dictionary format from API and object format
            if isinstance(item, dict):
                name = item.get('name', 'Unknown')
                size = item.get('size', 'Unknown')
                seeders = item.get('seeders', '0')
                leechers = item.get('leechers', '0')
                time = item.get('time', 'Unknown')
                provider = item.get('provider', 'Unknown')
                torrent_id = item.get('torrent_id', '')
            else:
                name = getattr(item, 'name', 'Unknown')
                size = getattr(item, 'size', 'Unknown')
                seeders = str(getattr(item, 'seeders', 0))
                leechers = str(getattr(item, 'leechers', 0))
                time = getattr(item, 'time', 'Unknown')
                provider = getattr(item, 'provider', 'Unknown')
                torrent_id = getattr(item, 'torrent_id', '')
            
            name_item = QTableWidgetItem(name)
            name_item.setToolTip(name)
            
            size_item = QTableWidgetItem(size)
            seeders_item = QTableWidgetItem(str(seeders))
            leechers_item = QTableWidgetItem(str(leechers))
            date_item = QTableWidgetItem(time)
            provider_item = QTableWidgetItem(provider)
            
            # Set colors for seeders/leechers
            seeders_item.setForeground(QColor("#4CAF50")) # Green
            leechers_item.setForeground(QColor("#F44336")) # Red

            self.results_table.setItem(row, 0, name_item)
            self.results_table.setItem(row, 1, size_item)
            self.results_table.setItem(row, 2, seeders_item)
            self.results_table.setItem(row, 3, leechers_item)
            self.results_table.setItem(row, 4, date_item)
            self.results_table.setItem(row, 5, provider_item)
            self.results_table.setItem(row, 6, QTableWidgetItem(torrent_id))
        
        self.results_table.resizeRowsToContents()

class FavoritesTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_widgets()
        self._init_layouts()

    def _init_widgets(self):
        self.favorites_table = QTableWidget()
        self.favorites_table.setColumnCount(6)
        self.favorites_table.setHorizontalHeaderLabels(["Name", "Category", "Size", "Seeders", "Leechers", "ID"])
        self.favorites_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.favorites_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.favorites_table.verticalHeader().setVisible(False)
        self.favorites_table.setColumnHidden(5, True)

        header = self.favorites_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self.add_favorite_button = QPushButton("Add to Favorites")
        self.add_favorite_button.setEnabled(False)
        self.remove_favorite_button = QPushButton("Remove from Favorites")
        self.remove_favorite_button.setEnabled(False)

    def _init_layouts(self):
        layout = QVBoxLayout(self)
        label = QLabel("Favorites:")
        label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.add_favorite_button)
        buttons_layout.addWidget(self.remove_favorite_button)
        buttons_layout.addStretch(1)
        
        layout.addWidget(label)
        layout.addWidget(self.favorites_table)
        layout.addLayout(buttons_layout)

    def populate_favorites(self, favorites):
        self.favorites_table.clearContents()
        self.favorites_table.setRowCount(len(favorites))

        for row, fav in enumerate(favorites):
            self.favorites_table.setItem(row, 0, QTableWidgetItem(fav.get("name", "N/A")))
            self.favorites_table.setItem(row, 1, QTableWidgetItem(fav.get("category", "N/A")))
            self.favorites_table.setItem(row, 2, QTableWidgetItem(fav.get("size", "N/A")))
            self.favorites_table.setItem(row, 3, QTableWidgetItem(str(fav.get("seeders", "N/A"))))
            self.favorites_table.setItem(row, 4, QTableWidgetItem(str(fav.get("leechers", "N/A"))))
            self.favorites_table.setItem(row, 5, QTableWidgetItem(fav.get("torrentId", "N/A")))
        
        self.favorites_table.resizeRowsToContents() 

class DetailsArea(QGroupBox):
    def __init__(self, title="Torrent Details", parent=None):
        super().__init__(title, parent)
        self._init_widgets()
        self._init_layouts()

    def _init_widgets(self):
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)

    def _init_layouts(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self.details_text)

    def update_details(self, html):
        self.details_text.setHtml(html)

    def clear_details(self):
        self.details_text.setHtml("<i>No details selected.</i>")

class ActionButtons(QGroupBox):
    def __init__(self, title="Actions", parent=None):
        super().__init__(title, parent)
        self._init_widgets()
        self._init_layouts()

    def _init_widgets(self):
        self.copy_magnet_button = QPushButton("Copy Magnet Link")
        self.download_button = QPushButton("Download with Magnet")
        self.add_favorite_button = QPushButton("Add to Favorites")
        self.set_buttons_enabled(False)

    def _init_layouts(self):
        layout = QVBoxLayout(self)
        layout.addWidget(self.copy_magnet_button)
        layout.addWidget(self.download_button)
        layout.addWidget(self.add_favorite_button)
        layout.addStretch(1)

    def set_buttons_enabled(self, enabled):
        self.copy_magnet_button.setEnabled(enabled)
        self.download_button.setEnabled(enabled)
        self.add_favorite_button.setEnabled(enabled)