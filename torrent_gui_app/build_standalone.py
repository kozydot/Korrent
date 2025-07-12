#!/usr/bin/env python3
"""
Korrent Standalone Builder
Creates a completely self-contained executable that includes the TorrentApi server.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def build_torrent_api_server():
    """Build the TorrentApi server if not already built."""
    print("🔨 Building TorrentApi server...")
    
    # Navigate to TorrentApi directory
    script_dir = Path(__file__).parent
    torrent_api_dir = script_dir.parent.parent / "TorrentApi"
    
    if not torrent_api_dir.exists():
        print("❌ TorrentApi directory not found!")
        print(f"   Expected: {torrent_api_dir}")
        return False
    
    # Check if server executable already exists
    server_exe = torrent_api_dir / "target" / "debug" / "api-server.exe"
    if server_exe.exists():
        print(f"✅ Server executable found: {server_exe}")
        return True
    
    # Try to build the server
    try:
        print("   Running cargo build...")
        result = subprocess.run(
            ["cargo", "build"],
            cwd=torrent_api_dir,
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode == 0:
            if server_exe.exists():
                print("✅ TorrentApi server built successfully!")
                return True
            else:
                print("❌ Build succeeded but executable not found!")
                return False
        else:
            print("❌ Failed to build TorrentApi server!")
            print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ Build timeout after 5 minutes!")
        return False
    except FileNotFoundError:
        print("❌ Cargo not found! Please install Rust and Cargo.")
        return False
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False

def create_standalone_executable():
    """Create the standalone executable with PyInstaller."""
    print("📦 Creating standalone executable...")
    
    script_dir = Path(__file__).parent
    torrent_api_dir = script_dir.parent.parent / "TorrentApi"
    server_exe = torrent_api_dir / "target" / "debug" / "api-server.exe"
    config_file = torrent_api_dir / "config.yaml"
    
    # Prepare PyInstaller command
    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed", 
        "--name", "Korrent",
        "--add-data", "favorites.json;.",
        "--add-data", "style.qss;.",
        "--exclude-module", "PyQt5"
    ]
    
    # Add server executable if it exists
    if server_exe.exists():
        cmd.extend(["--add-binary", f"{server_exe};."])
        print(f"✅ Including server: {server_exe}")
    else:
        print("⚠️ Server executable not found - will create limited executable")
    
    # Add config file if it exists
    if config_file.exists():
        cmd.extend(["--add-data", f"{config_file};."])
        print(f"✅ Including config: {config_file}")
    
    # Add application icon if it exists
    icon_path = script_dir.parent.parent / "image" / "image.png"
    if icon_path.exists():
        # Convert PNG to ICO for Windows executable
        ico_path = script_dir / "icon.ico"
        try:
            from PIL import Image
            img = Image.open(icon_path)
            img.save(ico_path, format='ICO', sizes=[(32, 32), (64, 64)])
            cmd.extend(["--icon", str(ico_path)])
            print(f"✅ Including icon: {ico_path}")
        except ImportError:
            print("⚠️ PIL not available, skipping icon conversion")
        except Exception as e:
            print(f"⚠️ Icon conversion failed: {e}")
    
    # Add the main script
    cmd.append("app.py")
    
    print("🚀 Running PyInstaller...")
    print(f"   Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, cwd=script_dir, check=True)
        print("✅ PyInstaller completed successfully!")
        
        # Check if executable was created
        exe_path = script_dir / "dist" / "Korrent.exe"
        if exe_path.exists():
            exe_size = exe_path.stat().st_size / (1024 * 1024)  # Size in MB
            print(f"✅ Executable created: {exe_path}")
            print(f"   Size: {exe_size:.1f} MB")
            
            # Create a simple README for distribution
            create_distribution_readme(script_dir / "dist")
            
            return True
        else:
            print("❌ Executable not found after build!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller failed with exit code {e.returncode}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def create_distribution_readme(dist_dir):
    """Create a README file for the distribution."""
    readme_content = """# Korrent - Torrent Search Application

Korrent is a standalone torrent search application that searches multiple torrent providers through a unified interface.

## Quick Start

1. Run Korrent.exe
2. Wait for automatic server startup (10-15 seconds)
3. Enter search terms and click Search
4. Copy magnet links or open directly in your torrent client

## Features

- Automatic server startup
- Multi-provider search (ThePirateBay, YTS, BitSearch)
- Modern interface with favorites management
- Magnet link handling
- No installation required

## Troubleshooting

- If Windows blocks the app: Right-click > Properties > Unblock > OK
- If antivirus flags it: Add to exclusions (false positive)
- If server fails to start: Try running as administrator
- Ensure your torrent client is installed for magnet link handling

## Credits

This application uses TorrentApi by Netfloex for torrent search functionality.
TorrentApi: https://github.com/Netfloex/TorrentApi

## Legal Notice

This software searches publicly available torrent files. Users must ensure legal rights to download content and respect copyright laws in their jurisdiction.

## Requirements

- Windows 10/11 (64-bit)
- Internet connection
- Torrent client (recommended: qBittorrent)
"""
    
    readme_path = dist_dir / "README.txt"
    try:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(readme_content)
        print(f"✅ Created distribution README: {readme_path}")
    except Exception as e:
        print(f"⚠️ Could not create README: {e}")

def main():
    """Main build process."""
    print("🏗️  Korrent Standalone Builder")
    print("=" * 50)
    
    # Step 1: Build TorrentApi server
    if not build_torrent_api_server():
        print("\n⚠️ Continuing without server - executable will have limited functionality")
    
    print()
    
    # Step 2: Create standalone executable
    if create_standalone_executable():
        print("\n🎉 Build completed successfully!")
        print("\nYour standalone executable is ready:")
        print("   📁 Location: dist/Korrent.exe")
        print("   📄 Documentation: dist/README.txt")
        print("\nYou can now distribute this executable to other users!")
    else:
        print("\n❌ Build failed!")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
