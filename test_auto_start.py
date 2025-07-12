#!/usr/bin/env python3
"""
Test script to verify the TorrentApi auto-start functionality.
"""

import sys
import os

# Add the torrent_gui_app directory to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
gui_app_dir = os.path.join(current_dir, 'torrent_gui_app')
sys.path.insert(0, gui_app_dir)

# Change to the GUI app directory so imports work correctly
os.chdir(gui_app_dir)

# Import and test the server manager
from app import TorrentApiServerManager

def test_server_manager():
    print("Testing TorrentApiServerManager...")
    
    manager = TorrentApiServerManager()
    
    print(f"Server executable found: {manager.server_executable}")
    
    if not manager.server_executable:
        print("❌ TorrentApi server executable not found!")
        return False
    
    print("Testing server startup...")
    success = manager.start_server()
    
    if success:
        print("✅ Server started successfully!")
        print("Testing server shutdown...")
        manager.stop_server()
        print("✅ Server stopped successfully!")
        return True
    else:
        print("❌ Failed to start server!")
        return False

if __name__ == "__main__":
    test_server_manager()
