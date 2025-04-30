# Korrent1337x

A simple desktop GUI application built with Python and PyQt6 to search for torrents on 1337x using the `py1337x` library.

## Features

*   Search for torrents on 1337x.
*   Filter search results by category.
*   Sort search results by time, size, seeders, or leechers (ascending/descending).
*   View torrent details (name, category, size, seeders, leechers, magnet link, etc.).
*   Copy magnet links to the clipboard.
*   Initiate torrent downloads by opening magnet links in the default torrent client.
*   Dark theme interface.
*   Smooth scrolling in the results list.

## Requirements

*   Python 3.x
*   PyQt6
*   py1337x
*   pyperclip
*   webbrowser

## Installation

1.  **Clone or download the repository/files.**
2.  **Navigate to the project directory** (`torrent_gui_app`) in your terminal.
3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
## Usage

Run the application from the `torrent_gui_app` directory:

```bash
python app.py
```

Enter your search query, optionally select category/sort options, and click "Search". Select a result from the table to view details. Use the buttons at the bottom to copy the magnet link or start the download.

## Acknowledgements

This application relies heavily on the excellent `py1337x` library by Hemanta Pokharel for interacting with 1337x.

*   **py1337x GitHub:** [https://github.com/hemantapkh/1337x](https://github.com/hemantapkh/1337x)
