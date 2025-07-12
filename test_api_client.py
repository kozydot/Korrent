#!/usr/bin/env python3
"""
Test script for the TorrentApi client integration
"""

import sys
from torrent_gui_app.api_client import TorrentApiClient, TorrentInfo

def test_api_client():
    """Test the TorrentApi client functionality"""
    
    # Initialize the API client
    print("Initializing TorrentApi client...")
    client = TorrentApiClient(base_url="http://localhost:8000")
    
    # Test search functionality
    print("\n1. Testing search functionality...")
    try:
        results = client.search("one piece", category="Any", sort_by="seeders", order="desc")
        print(f"   Found {len(results)} results")
        
        if results:
            # Display first result
            first = results[0]
            print(f"\n   First result:")
            print(f"   - Name: {first['name']}")
            print(f"   - Size: {first['size']}")
            print(f"   - Seeders: {first['seeders']}")
            print(f"   - Leechers: {first['leechers']}")
            print(f"   - Category: {first['category']}")
            print(f"   - Time: {first['time']}")
            print(f"   - Has magnet: {'Yes' if first.get('magnet_link') else 'No'}")
            
            # Test TorrentInfo creation
            print("\n2. Testing TorrentInfo object creation...")
            info = TorrentInfo(first)
            print(f"   TorrentInfo created successfully")
            print(f"   - ID: {info.torrent_id}")
            print(f"   - Name: {info.name}")
            print(f"   - Size: {info.size}")
            print(f"   - Magnet available: {'Yes' if info.magnet_link else 'No'}")
        else:
            print("   No results found - check if TorrentApi server is running")
            
    except Exception as e:
        print(f"   Error: {e}")
        return False
    
    # Test category mapping
    print("\n3. Testing category mapping...")
    categories = ["Any", "Movies/TV", "Music", "Games", "Apps", "Other"]
    for cat in categories:
        try:
            results = client.search("test", category=cat)
            print(f"   {cat} -> Mapped successfully")
        except Exception as e:
            print(f"   {cat} -> Error: {e}")
    
    # Test sort mapping
    print("\n4. Testing sort options mapping...")
    sort_options = ["time", "size", "seeders", "leechers"]
    for sort in sort_options:
        try:
            results = client.search("test", sort_by=sort)
            print(f"   {sort} -> Mapped successfully")
        except Exception as e:
            print(f"   {sort} -> Error: {e}")
    
    print("\n✅ API client test completed!")
    return True

if __name__ == "__main__":
    print("TorrentApi Client Test Script")
    print("=" * 40)
    print("Make sure the TorrentApi server is running at http://localhost:8000")
    print("=" * 40)
    
    success = test_api_client()
    sys.exit(0 if success else 1)