@echo off
echo Starting Korrent with TorrentApi...
echo.
echo Make sure TorrentApi is running at http://localhost:8000
echo You can start it with: cd ..\TorrentApi && cargo run --bin api-server
echo.
echo Starting Korrent GUI...
cd torrent_gui_app
python app.py
pause