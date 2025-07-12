# Korrent

A powerful desktop torrent search application built with Python and PyQt6, featuring automatic server management and a modern user interface. Search across multiple torrent providers with a single click.

## ✨ Features

### 🔍 **Multi-Provider Search**
- Search across **multiple torrent sources** (ThePirateBay, YTS, BitSearch)
- **Unified search interface** with provider-specific results
- **Real-time search** with background processing
- **Advanced filtering** by category, size, and quality

### 🚀 **Automatic Server Management**
- **Auto-start TorrentApi server** when launching the application
- **Visual server status** indicators with real-time updates
- **Graceful shutdown** and cleanup when closing
- **No manual server setup** required

### 🎨 **Modern User Interface**
- **Dark theme** with professional styling
- **Tabbed interface** for search results and favorites
- **Detailed torrent information** with health indicators
- **Enhanced visual feedback** and status updates

### 💾 **Advanced Features**
- **Favorites management** - save and organize your preferred torrents
- **Search history** with auto-completion
- **Magnet link handling** - copy or open directly in torrent client
- **Comprehensive torrent details** with quality detection
- **Standalone executable** generation for easy distribution

## 📸 Screenshot

![Application Screenshot](image/image.png)

## 🏗️ Architecture

This application consists of two main components:

### **1. Korrent GUI Application** (`torrent_gui_app/`)
- **Python/PyQt6** desktop application
- **Modern tabbed interface** with search and favorites
- **Automatic server management** and status monitoring
- **Advanced search filtering** and result display

### **2. TorrentApi Server** (`TorrentApi/`)
- **Rust-based GraphQL API** server
- **Multi-provider torrent search** backend
- **High-performance** concurrent searching
- **RESTful API** with comprehensive torrent data

## 🚦 Quick Start

### **Option 1: Use Pre-built Executable (Recommended)**
1. Download the latest release from the [Releases page]
2. Extract the ZIP file
3. Double-click `Korrent.exe` to start
4. **No installation or setup required!**

### **Option 2: Run from Source**
1. **Clone the repository:**
   ```bash
   git clone https://github.com/kozydot/Korrent1337x.git
   cd Korrent1337x
   ```

2. **Install Python dependencies:**
   ```bash
   cd torrent_gui_app
   pip install -r requirements.txt
   ```

3. **Build TorrentApi server:**
   ```bash
   cd ../TorrentApi
   cargo build
   ```

4. **Run the application:**
   ```bash
   cd ../torrent_gui_app
   python app.py
   ```

## 🛠️ Building Standalone Executable

Create your own standalone executable:

```bash
cd torrent_gui_app
python build_standalone.py
```

Or use the batch file:
```bash
build.bat
```

The executable will be created in `dist/Korrent.exe` with all dependencies bundled.

## 📋 Requirements

### **For Running from Source:**
- **Python 3.8+**
- **Rust 1.70+** (for building TorrentApi server)
- **PyQt6, requests, pyperclip** (automatically installed)

### **For Pre-built Executable:**
- **Windows 10/11** (64-bit)
- **No additional requirements**

## 🎯 Usage

1. **Launch** Korrent (executable or `python app.py`)
2. **Wait** for the server status to show "✅ Server running"
3. **Enter** your search query in the search box
4. **Select** providers and filters (optional)
5. **Click** "Search" to find torrents
6. **Select** a result to view detailed information
7. **Copy** magnet links or **open** them in your torrent client
8. **Add** favorites for easy access later

### 🔧 **Advanced Features:**
- **Test Connection:** Verify server connectivity
- **Provider Selection:** Choose specific torrent sources
- **Search History:** Access previous searches
- **Favorites Management:** Save and organize torrents

## 🛡️ Legal Notice

This application is designed for searching **publicly available torrent files**. Users are responsible for ensuring they have legal rights to download any content. **Respect copyright laws** in your jurisdiction.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## 📄 License

This project is open source. Please check individual component licenses:
- **Korrent GUI:** MIT License
- **TorrentApi:** Check TorrentApi repository for license details

## 🙏 Acknowledgements

- **TorrentApi** - Rust-based GraphQL torrent search API
- **PyQt6** - Cross-platform GUI framework
- **Various torrent providers** for making content discoverable
