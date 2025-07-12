import sys
import os # for path stuff
import threading
import webbrowser
import pyperclip
import json
import subprocess
import time
import atexit
from typing import Optional
from api_client import TorrentApiClient, TorrentInfo  # Import our new API client
from widgets import SearchControls, DetailsArea, ResultsTab, FavoritesTab, ActionButtons

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QStatusBar, QMessageBox, QListWidgetItem,
    QSizePolicy, QComboBox, QTableWidget, QTableWidgetItem, # for the results table
    QAbstractItemView, QHeaderView, QCompleter, QTabWidget, QGroupBox, QFileDialog # table display options
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt, QThread, QStringListModel
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen, QPolygon, QFont # for the window icon

# --- TorrentApi Server Manager ---
class TorrentApiServerManager:
    """Manages the TorrentApi server process."""
    
    def __init__(self):
        self.process = None
        self.api_url = "http://localhost:8000"
        self.server_executable = None
        self.server_dir = None
        self._setup_bundled_server()
        
    def _setup_bundled_server(self):
        """Setup bundled TorrentApi server for standalone executable."""
        # Check if running as bundled executable (PyInstaller sets sys._MEIPASS)
        if getattr(sys, 'frozen', False):
            # Running as bundled executable
            bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            self.server_executable = os.path.join(bundle_dir, "api-server.exe")
            self.server_dir = bundle_dir
            
            # Create a temporary directory for server files
            import tempfile
            self.temp_dir = tempfile.mkdtemp(prefix="korrent_server_")
            self.server_dir = self.temp_dir
            
            # Copy server executable to temp directory if it exists in bundle
            if os.path.exists(self.server_executable):
                import shutil
                temp_server_path = os.path.join(self.temp_dir, "api-server.exe")
                shutil.copy2(self.server_executable, temp_server_path)
                self.server_executable = temp_server_path
                print(f"Using bundled TorrentApi server: {self.server_executable}")
            else:
                # Server not bundled, try to find it in standard locations
                self._find_server_executable()
        else:
            # Running from source
            self._find_server_executable()
            
        # Ensure config file exists
        self._ensure_config_file()
        
    def _find_server_executable(self):
        """Find the TorrentApi server executable in development environment."""
        # Get the current script directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Navigate to the TorrentApi directory (assuming it's in the parent directory)
        torrent_api_dir = os.path.join(current_dir, "..", "..", "TorrentApi")
        server_exe_path = os.path.join(torrent_api_dir, "target", "debug", "api-server.exe")
        
        if os.path.exists(server_exe_path):
            self.server_executable = os.path.abspath(server_exe_path)
            self.server_dir = os.path.dirname(self.server_executable)
            print(f"Found TorrentApi server at: {self.server_executable}")
        else:
            print(f"TorrentApi server not found at: {server_exe_path}")
            # Try alternative paths
            alt_paths = [
                os.path.join(current_dir, "..", "..", "TorrentApi", "target", "release", "api-server.exe"),
                os.path.join(current_dir, "..", "TorrentApi", "target", "debug", "api-server.exe"),
                os.path.join(current_dir, "TorrentApi", "target", "debug", "api-server.exe"),
            ]
            
            for alt_path in alt_paths:
                if os.path.exists(alt_path):
                    self.server_executable = os.path.abspath(alt_path)
                    self.server_dir = os.path.dirname(self.server_executable)
                    print(f"Found TorrentApi server at alternative path: {self.server_executable}")
                    break
                    
    def _ensure_config_file(self):
        """Ensure a config.yaml file exists for the server."""
        if not self.server_dir:
            return
            
        config_path = os.path.join(self.server_dir, "config.yaml")
        
        if not os.path.exists(config_path):
            # Create a default config file
            default_config = """# TorrentApi Configuration
# This config is automatically generated for Korrent

# qBittorrent settings (optional - only needed if you want to auto-download)
qbittorrent:
    username: admin
    password: adminadmin
    url: http://localhost:8080

# Download paths (optional)
movies_path: ./downloads
remote_download_path: ./downloads
local_download_path: ./downloads

# Server settings
server:
    host: 127.0.0.1
    port: 8000
"""
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(default_config)
                print(f"Created default config file: {config_path}")
            except Exception as e:
                print(f"Warning: Could not create config file: {e}")
                
    def _create_portable_environment(self):
        """Create a portable environment for the server."""
        if not self.server_dir:
            return
            
        # Create downloads directory
        downloads_dir = os.path.join(self.server_dir, "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
    
    def is_server_running(self):
        """Check if the TorrentApi server is already running."""
        try:
            api_client = TorrentApiClient(base_url=self.api_url, timeout=3)
            result = api_client.test_connection()
            return result['status'] == 'success'
        except:
            return False
    
    def start_server(self):
        """Start the TorrentApi server if it's not already running."""
        if self.is_server_running():
            print("TorrentApi server is already running")
            return True
            
        if not self.server_executable:
            print("❌ TorrentApi server executable not found.")
            # Try to provide helpful guidance
            if getattr(sys, 'frozen', False):
                print("   Server was not bundled with the executable.")
                print("   Please ensure the server is built and available.")
            else:
                print("   Please build the TorrentApi project first.")
                print("   Run: cargo build in the TorrentApi directory")
            return False
            
        try:
            print(f"Starting TorrentApi server from: {self.server_executable}")
            
            # Create portable environment
            self._create_portable_environment()
            
            # Use the server directory as working directory
            working_dir = self.server_dir if self.server_dir else os.path.dirname(self.server_executable)
            
            # Start the server process with minimal output
            self.process = subprocess.Popen(
                [self.server_executable],
                cwd=working_dir,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            # Wait a moment for the server to start
            print("Waiting for TorrentApi server to start...")
            for i in range(15):  # Wait up to 15 seconds (increased timeout)
                time.sleep(1)
                if self.is_server_running():
                    print("✅ TorrentApi server started successfully!")
                    # Register cleanup function
                    atexit.register(self.stop_server)
                    return True
                print(f"  Waiting... ({i+1}/15)")
            
            print("❌ TorrentApi server failed to start within timeout")
            # Try to get some error information
            if self.process.poll() is not None:
                print(f"   Server process exited with code: {self.process.returncode}")
            return False
            
        except Exception as e:
            print(f"❌ Failed to start TorrentApi server: {str(e)}")
            return False
    
    def stop_server(self):
        """Stop the TorrentApi server if it was started by this application."""
        if self.process and self.process.poll() is None:
            try:
                print("Stopping TorrentApi server...")
                self.process.terminate()
                
                # Wait for graceful shutdown
                try:
                    self.process.wait(timeout=5)
                    print("✅ TorrentApi server stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if it doesn't stop gracefully
                    self.process.kill()
                    self.process.wait()
                    print("⚡ TorrentApi server force-stopped")
                    
            except Exception as e:
                print(f"Error stopping TorrentApi server: {str(e)}")
            finally:
                self.process = None
                
        # Cleanup temporary directory if we created one
        if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
            try:
                import shutil
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                print(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                print(f"Warning: Could not cleanup temp directory: {e}")

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
    def __init__(self, query, category=None, sort_by=None, order='desc', providers=None, api_url=None): # needs search parameters
        super().__init__()
        self.query = query
        self.category = category
        self.sort_by = sort_by
        self.order = order
        self.providers = providers
        self.api_url = api_url or "http://localhost:8000"
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.status_update.emit(f"Searching for '{self.query}'...")
            
            # Use our new TorrentApi client with longer timeout
            api_client = TorrentApiClient(base_url=self.api_url, timeout=60)
            
            # get the search results from the API
            items = api_client.search(self.query, category=self.category, sort_by=self.sort_by, order=self.order, providers=self.providers)
            
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
    def __init__(self, torrent_info):
        super().__init__()
        self.torrent_info = torrent_info
        self.signals = WorkerSignals()

    def run(self):
        try:
            self.signals.status_update.emit(f"Processing details for: {self.torrent_info.get('name', 'Unknown')}...")
            
            # Create TorrentInfo object from the stored data
            details = TorrentInfo(self.torrent_info)
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
        self.search_results_cache = {}  # Cache search results by torrent ID
        self.search_worker = None # Search worker thread
        self.details_worker = None # Details worker thread
        
        # --- TorrentApi server manager ---
        self.server_manager = TorrentApiServerManager()
        
        # --- ui initialization ---
        self.initUI()

        # --- start TorrentApi server ---
        self.start_torrent_api_server()

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
        self.search_controls.test_connection_button.clicked.connect(self.test_api_connection)
        self.search_controls.search_entry.returnPressed.connect(self.start_search)
        
        clear_history_button = QPushButton("Clear History")
        clear_history_button.clicked.connect(self.clear_search_history)
        clear_history_button.setToolTip("Clear search history")
        clear_history_button.setMinimumWidth(100)
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
        
        # Clear search results cache
        self.search_results_cache = {}
        
        # a new search worker is created with the search parameters
        self.search_worker = SearchWorker(
            query,
            category=params['category'],
            sort_by=params['sort_by'],
            order=params['order'],
            providers=params.get('providers'),
            api_url=params.get('api_url', 'http://localhost:8000')
        )
        self.search_worker.signals.search_finished.connect(self.update_search_results)
        self.search_worker.signals.error.connect(self.show_error)
        self.search_worker.signals.status_update.connect(self.update_status)
        self.search_worker.start()

    def update_search_results(self, items):
        """Populates the search results table with data from the search worker."""
        # Cache the search results for details display
        for item in items:
            # Try multiple possible ID fields for caching
            torrent_id = item.get('torrent_id') or item.get('infoHash') or item.get('id') or item.get('name', '')
            if torrent_id:
                self.search_results_cache[torrent_id] = item
                # Also cache by name as a fallback
                name = item.get('name', '')
                if name and name != torrent_id:
                    self.search_results_cache[name] = item
                
                # Debug: Print magnet link availability
                magnet = item.get('magnet_link') or item.get('magnet', '')
                if magnet:
                    print(f"Cached torrent '{name}' with magnet link")
                else:
                    print(f"Cached torrent '{name}' without magnet link")
        
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
            self.details_area.clear_details()
            return

        selected_row = selected_items[0].row()
        
        # Get torrent data directly from table - more reliable than caching
        name_item = self.search_tab.results_table.item(selected_row, 0)
        size_item = self.search_tab.results_table.item(selected_row, 1) 
        seeders_item = self.search_tab.results_table.item(selected_row, 2)
        leechers_item = self.search_tab.results_table.item(selected_row, 3)
        date_item = self.search_tab.results_table.item(selected_row, 4)
        provider_item = self.search_tab.results_table.item(selected_row, 5)
        torrent_id_item = self.search_tab.results_table.item(selected_row, 6)
        
        if not name_item:
            self.details_area.clear_details()
            return
            
        # Build torrent info directly without worker thread
        torrent_info = {
            "name": name_item.text(),
            "size": size_item.text() if size_item else "Unknown",
            "seeders": seeders_item.text() if seeders_item else "0",
            "leechers": leechers_item.text() if leechers_item else "0", 
            "time": date_item.text() if date_item else "Unknown",
            "provider": provider_item.text() if provider_item else "Unknown",
            "torrent_id": torrent_id_item.text() if torrent_id_item else "",
            "category": "Unknown"
        }
        
        # Check cache for additional details like magnet link
        torrent_id = torrent_info["torrent_id"]
        if torrent_id and torrent_id in self.search_results_cache:
            cached_info = self.search_results_cache[torrent_id]
            torrent_info.update({
                "magnet_link": cached_info.get("magnet_link", cached_info.get("magnet", "")),
                "category": cached_info.get("category", "Unknown"),
                "description": cached_info.get("description", "No description available."),
                "uploader": cached_info.get("uploader", "TorrentApi")
            })
        
        # Also try to find by name if torrent_id lookup failed
        if not torrent_info.get("magnet_link") and torrent_info["name"] in self.search_results_cache:
            cached_info = self.search_results_cache[torrent_info["name"]]
            torrent_info.update({
                "magnet_link": cached_info.get("magnet_link", cached_info.get("magnet", "")),
                "category": cached_info.get("category", "Unknown"),
                "description": cached_info.get("description", "No description available."),
                "uploader": cached_info.get("uploader", "TorrentApi")
            })
        
        # Create TorrentInfo object and display details immediately
        try:
            self.current_torrent_info = TorrentInfo(torrent_info)
            self.update_details_display(self.current_torrent_info)
            self.favorites_tab.add_favorite_button.setEnabled(True)
            self.set_action_buttons_enabled(True)
        except Exception as e:
            self.show_error("Details Error", f"Failed to display details: {str(e)}")
            self.details_area.clear_details()

    def update_details_display(self, info):
        """
        Updates the details view with information from the torrent info.
        """
        self.current_torrent_info = info
        if info:
            # Check if this torrent is already a favorite
            is_favorite = any(fav.get('torrentId') == info.torrent_id for fav in self.favorites)
            self.favorites_tab.add_favorite_button.setText("In Favorites" if is_favorite else "Add to Favorites")
            self.favorites_tab.add_favorite_button.setEnabled(not is_favorite)
            
            # Update action buttons favorite button state
            self.action_buttons.add_favorite_button.setText("In Favorites" if is_favorite else "Add to Favorites")
            self.action_buttons.add_favorite_button.setEnabled(not is_favorite)

            self.set_action_buttons_enabled(True)
            
            # Create enhanced HTML details view
            magnet_status = "✅ Available" if info.magnet_link else "❌ Not Available"
            magnet_color = "#4CAF50" if info.magnet_link else "#F44336"
            
            # Determine quality based on filename
            quality = "Unknown"
            if "2160p" in info.name or "4K" in info.name.upper():
                quality = "4K Ultra HD"
                quality_color = "#FFD700"
            elif "1080p" in info.name:
                quality = "Full HD (1080p)"
                quality_color = "#4CAF50"
            elif "720p" in info.name:
                quality = "HD (720p)"
                quality_color = "#2196F3"
            elif "480p" in info.name:
                quality = "SD (480p)"
                quality_color = "#FF9800"
            else:
                quality = "Standard"
                quality_color = "#9E9E9E"
            
            # Determine file type
            file_type = "Unknown"
            if "BRRip" in info.name or "BluRay" in info.name:
                file_type = "BluRay Rip"
            elif "WEBRip" in info.name or "WEB-DL" in info.name:
                file_type = "Web Rip"
            elif "DVDRip" in info.name:
                file_type = "DVD Rip"
            elif "CAM" in info.name:
                file_type = "Camera"
            elif "TS" in info.name:
                file_type = "Telesync"
            
            # Calculate ratio
            try:
                seeders = int(info.seeders) if str(info.seeders).isdigit() else 0
                leechers = int(info.leechers) if str(info.leechers).isdigit() else 0
                ratio = seeders / max(leechers, 1)
                ratio_text = f"{ratio:.2f}"
                ratio_color = "#4CAF50" if ratio > 2 else "#FF9800" if ratio > 1 else "#F44336"
            except:
                ratio_text = "N/A"
                ratio_color = "#9E9E9E"
                
            details_html = f"""
                <div style='font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #1e1e1e 0%, #2d2d2d 100%); color: #ffffff; padding: 20px; border-radius: 12px; margin: 0;'>
                    
                    <!-- Title Section -->
                    <div style='background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%); padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 4px 8px rgba(0,0,0,0.3);'>
                        <h2 style='margin: 0; color: white; font-size: 16px; font-weight: 600; text-shadow: 0 1px 2px rgba(0,0,0,0.5);'>
                            📁 {info.name}
                        </h2>
                    </div>
                    
                    <!-- Quick Stats Row -->
                    <div style='display: flex; justify-content: space-between; margin-bottom: 20px; gap: 10px;'>
                        <div style='background: #363636; padding: 12px; border-radius: 8px; text-align: center; flex: 1; border-left: 4px solid #4CAF50;'>
                            <div style='font-size: 20px; font-weight: bold; color: #4CAF50;'>{info.seeders}</div>
                            <div style='font-size: 11px; color: #aaa; text-transform: uppercase;'>Seeders</div>
                        </div>
                        <div style='background: #363636; padding: 12px; border-radius: 8px; text-align: center; flex: 1; border-left: 4px solid #F44336;'>
                            <div style='font-size: 20px; font-weight: bold; color: #F44336;'>{info.leechers}</div>
                            <div style='font-size: 11px; color: #aaa; text-transform: uppercase;'>Leechers</div>
                        </div>
                        <div style='background: #363636; padding: 12px; border-radius: 8px; text-align: center; flex: 1; border-left: 4px solid {ratio_color};'>
                            <div style='font-size: 20px; font-weight: bold; color: {ratio_color};'>{ratio_text}</div>
                            <div style='font-size: 11px; color: #aaa; text-transform: uppercase;'>Ratio</div>
                        </div>
                    </div>
                    
                    <!-- Main Info Grid -->
                    <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;'>
                        
                        <!-- File Information -->
                        <div style='background: #363636; padding: 15px; border-radius: 8px; border-left: 4px solid #2196F3;'>
                            <h3 style='color: #2196F3; margin: 0 0 12px 0; font-size: 14px; font-weight: 600;'>📄 File Information</h3>
                            <div style='font-size: 12px; line-height: 1.6;'>
                                <div style='margin-bottom: 8px;'><strong>Size:</strong> <span style='color: #FFD700;'>{info.size}</span></div>
                                <div style='margin-bottom: 8px;'><strong>Quality:</strong> <span style='color: {quality_color};'>{quality}</span></div>
                                <div style='margin-bottom: 8px;'><strong>Type:</strong> <span style='color: #9C27B0;'>{file_type}</span></div>
                                <div style='margin-bottom: 8px;'><strong>Category:</strong> <span style='color: #00BCD4;'>{info.category}</span></div>
                            </div>
                        </div>
                        
                        <!-- Source Information -->
                        <div style='background: #363636; padding: 15px; border-radius: 8px; border-left: 4px solid #FF9800;'>
                            <h3 style='color: #FF9800; margin: 0 0 12px 0; font-size: 14px; font-weight: 600;'>🌐 Source Information</h3>
                            <div style='font-size: 12px; line-height: 1.6;'>
                                <div style='margin-bottom: 8px;'><strong>Provider:</strong> <span style='color: #00BCD4;'>{info.provider}</span></div>
                                <div style='margin-bottom: 8px;'><strong>Uploader:</strong> <span style='color: #FFC107;'>{info.uploader}</span></div>
                                <div style='margin-bottom: 8px;'><strong>Date Added:</strong> <span style='color: #E91E63;'>{info.date_uploaded}</span></div>
                                <div style='margin-bottom: 8px;'><strong>Files:</strong> <span style='color: #8BC34A;'>{getattr(info, "file_count", "1")}</span></div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Magnet Link Section -->
                    <div style='background: #363636; padding: 15px; border-radius: 8px; border-left: 4px solid {magnet_color}; margin-bottom: 15px;'>
                        <h3 style='color: {magnet_color}; margin: 0 0 10px 0; font-size: 14px; font-weight: 600;'>🧲 Magnet Link</h3>
                        <div style='display: flex; align-items: center; gap: 10px;'>
                            <span style='color: {magnet_color}; font-weight: bold;'>{magnet_status}</span>
                            {f'<div style="background: #2b2b2b; padding: 8px; border-radius: 4px; border: 1px solid #555; font-family: monospace; font-size: 10px; word-break: break-all; color: #81C784; flex: 1; max-height: 60px; overflow-y: auto;">{info.magnet_link}</div>' if info.magnet_link else '<span style="color: #666; font-style: italic;">No magnet link available for this torrent</span>'}
                        </div>
                    </div>
                    
                    <!-- Info Hash -->
                    <div style='background: #363636; padding: 15px; border-radius: 8px; border-left: 4px solid #607D8B;'>
                        <h3 style='color: #607D8B; margin: 0 0 10px 0; font-size: 14px; font-weight: 600;'>🔍 Technical Details</h3>
                        <div style='font-size: 12px; line-height: 1.6;'>
                            <div style='margin-bottom: 8px;'><strong>Info Hash:</strong> <span style='color: #90A4AE; font-family: monospace; font-size: 10px;'>{info.torrent_id}</span></div>
                            <div style='margin-bottom: 8px;'><strong>Health:</strong> 
                                <span style='color: {"#4CAF50" if int(info.seeders or 0) > 10 else "#FF9800" if int(info.seeders or 0) > 0 else "#F44336"};'>
                                    {"Excellent" if int(info.seeders or 0) > 50 else "Good" if int(info.seeders or 0) > 10 else "Fair" if int(info.seeders or 0) > 0 else "Poor"}
                                </span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Warning Notice -->
                    {f'<div style="background: linear-gradient(135deg, #F44336 0%, #d32f2f 100%); padding: 12px; border-radius: 8px; margin-top: 15px; border: 1px solid #F44336;"><div style="display: flex; align-items: center; gap: 8px;"><span style="font-size: 16px;">⚠️</span><div style="font-size: 11px; color: #FFCDD2; line-height: 1.4;"><strong>Legal Notice:</strong> Ensure you have the legal right to download this content. Respect copyright laws in your jurisdiction.</div></div></div>' if info.magnet_link else ''}
                </div>
            """
            
            self.details_area.update_details(details_html)
            
            # Update status with magnet availability and health info
            health = "Excellent" if int(info.seeders or 0) > 50 else "Good" if int(info.seeders or 0) > 10 else "Fair" if int(info.seeders or 0) > 0 else "Poor"
            if info.magnet_link:
                self.update_status(f"Selected: {info.name} - Health: {health} - Magnet available")
            else:
                self.update_status(f"Selected: {info.name} - Health: {health} - No magnet link")
                
        else:
            self.details_area.clear_details()
            self.set_action_buttons_enabled(False)
            self.favorites_tab.add_favorite_button.setEnabled(False)

    def copy_magnet(self):
        """Copies the magnet link of the selected torrent to the clipboard."""
        if self.current_torrent_info and self.current_torrent_info.magnet_link:
            try:
                pyperclip.copy(self.current_torrent_info.magnet_link)
                self.update_status("✅ Magnet link copied to clipboard.")
            except Exception as e:
                self.show_error("Copy Error", f"Failed to copy magnet link: {str(e)}")
        else:
            self.show_error("Copy Error", "No magnet link available to copy.")

    def download_torrent_via_magnet(self):
        """Opens the magnet link in the default torrent client."""
        if self.current_torrent_info and self.current_torrent_info.magnet_link:
            try:
                webbrowser.open(self.current_torrent_info.magnet_link)
                self.update_status("✅ Opening magnet link in default torrent client...")
            except Exception as e:
                self.show_error("Download Error", f"Failed to open magnet link: {str(e)}")
        else:
            self.show_error("Download Error", "No magnet link available for this torrent.")
            
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
        self.stop_torrent_api_server()  # Ensure the server is stopped
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
                # Get full torrent info from cache
                torrent_data = self.search_results_cache.get(self.current_torrent_info.torrent_id, {})
                
                # Add necessary info to favorites list
                self.favorites.append({
                    'torrentId': self.current_torrent_info.torrent_id,
                    'name': self.current_torrent_info.name,
                    'category': self.current_torrent_info.category,
                    'size': self.current_torrent_info.size,
                    'seeders': self.current_torrent_info.seeders,
                    'leechers': self.current_torrent_info.leechers,
                    'magnet_link': torrent_data.get('magnet_link', self.current_torrent_info.magnet_link),
                    'time': torrent_data.get('time', self.current_torrent_info.date_uploaded)
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
        
        # Find the favorite torrent info
        favorite_info = None
        for fav in self.favorites:
            if fav.get('torrentId') == torrent_id:
                favorite_info = fav
                break
        
        if not favorite_info:
            self.show_error("Favorite Error", "Favorite information not found.")
            return
        
        # When a favorite is selected, enable the remove button
        self.favorites_tab.remove_favorite_button.setEnabled(True)

        # Use the details worker with the stored favorite data
        self._stop_worker(self.details_worker)
        self.details_worker = DetailsWorker(favorite_info)
        self.details_worker.signals.details_finished.connect(self.update_details_display)
        self.details_worker.signals.error.connect(self.show_error)
        self.details_worker.signals.status_update.connect(self.update_status)
        self.details_worker.start()

    def start_torrent_api_server(self):
        """Start the TorrentApi server automatically with better error handling."""
        print("Initializing TorrentApi server...")
        
        # Show status in UI
        if hasattr(self, 'search_controls'):
            self.search_controls.update_server_status('starting', 'Starting server...')
        
        # Show status in status bar if it exists
        if hasattr(self, 'status_bar'):
            self.status_bar.showMessage("Starting TorrentApi server...")
        
        # Start the server in a separate thread to avoid blocking UI
        def start_server_thread():
            success = self.server_manager.start_server()
            
            # Update UI from main thread using Qt's signal mechanism would be better,
            # but for simplicity we'll update directly (should work since PyQt is thread-safe for simple operations)
            if hasattr(self, 'search_controls'):
                if success:
                    self.search_controls.update_server_status('running', 'Server running')
                    if hasattr(self, 'status_bar'):
                        self.status_bar.showMessage("✅ TorrentApi server started successfully", 3000)
                else:
                    self.search_controls.update_server_status('error', 'Server not available')
                    if hasattr(self, 'status_bar'):
                        self.status_bar.showMessage("⚠️ TorrentApi server unavailable - search functionality limited", 5000)
                    
                    # Show helpful message to user
                    self._show_server_unavailable_message()
            
        # Start in background thread
        server_thread = threading.Thread(target=start_server_thread, daemon=True)
        server_thread.start()
        
    def _show_server_unavailable_message(self):
        """Show a helpful message when the server is not available."""
        # Use a timer to show the message after the UI is fully loaded
        from PyQt6.QtCore import QTimer
        
        def show_message():
            if getattr(sys, 'frozen', False):
                # Running as executable
                message = """⚠️ TorrentApi Server Not Available

The torrent search server could not be started. This may happen if:

• The server was not bundled with this executable
• Windows Security/Antivirus is blocking the server
• The server files are corrupted

You can still:
• Use the application interface 
• Test connection to external servers
• View this message by clicking 'Test Connection'

For full functionality, try:
• Running as administrator
• Adding exception to antivirus
• Downloading the complete package"""
            else:
                # Running from source
                message = """⚠️ TorrentApi Server Not Available

The torrent search server could not be started. 

To fix this:
• Build the TorrentApi project: cargo build
• Ensure the server executable exists
• Check the project structure

Search functionality will be limited until the server is available."""
            
            QMessageBox.information(
                self,
                "Server Status",
                message
            )
        
        # Show message after 2 seconds to ensure UI is ready
        QTimer.singleShot(2000, show_message)

    def test_api_connection(self):
        """Test connection to the TorrentApi server."""
        params = self.search_controls.get_search_parameters()
        api_url = params['api_url']
        
        # Show testing status
        self.status_bar.showMessage("Testing connection...")
        self.search_controls.update_server_status('starting', 'Testing...')
        
        try:
            api_client = TorrentApiClient(base_url=api_url, timeout=10)
            result = api_client.test_connection()
            
            if result['status'] == 'success':
                self.status_bar.showMessage(f"✅ {result['message']}", 5000)
                self.search_controls.update_server_status('running', 'Server running')
                QMessageBox.information(
                    self, 
                    "Connection Test", 
                    f"✅ Success!\n\n{result['message']}\nURL: {result['url']}"
                )
            else:
                self.status_bar.showMessage(f"❌ Connection failed", 5000)
                self.search_controls.update_server_status('error', 'Connection failed')
                QMessageBox.warning(
                    self,
                    "Connection Test Failed",
                    f"❌ Connection failed!\n\nError: {result['message']}\nURL: {result['url']}\n\nPlease check:\n• Is the TorrentApi server running?\n• Is the URL correct?\n• Are there any firewall issues?"
                )
        
        except Exception as e:
            error_msg = f"Test failed: {str(e)}"
            self.status_bar.showMessage("❌ Connection test failed", 5000)
            self.search_controls.update_server_status('error', 'Test failed')
            QMessageBox.critical(
                self,
                "Connection Test Error", 
                f"❌ Connection test failed!\n\nError: {error_msg}\n\nPlease check your network connection and server status."
            )

    def stop_torrent_api_server(self):
        """Stop the TorrentApi server when the application closes."""
        if hasattr(self, 'server_manager'):
            self.server_manager.stop_server()

# --- application entry point ---
def main():
    app = QApplication(sys.argv)
    ex = TorrentApp()
    ex.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()