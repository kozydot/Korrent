#!/usr/bin/env python3
"""
Test script to check magnet link availability in search results
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_client import TorrentApiClient

def test_magnet_links():
    """Test if search results include magnet links"""
    print("Testing magnet link availability...")
    
    client = TorrentApiClient(base_url="http://localhost:8000", timeout=30)
    
    try:
        # Test with PirateBay only since others are failing
        results = client.search("avengers", providers=["PirateBay"])
        print(f"Found {len(results)} results from PirateBay")
        
        if results:
            # Check first few results for magnet links
            for i, result in enumerate(results[:3]):
                print(f"\nResult {i+1}:")
                print(f"  Name: {result.get('name', 'Unknown')}")
                print(f"  Provider: {result.get('provider', 'Unknown')}")
                print(f"  Size: {result.get('size', 'Unknown')}")
                print(f"  Seeders: {result.get('seeders', 'Unknown')}")
                
                # Check for magnet link
                magnet = result.get('magnet_link') or result.get('magnet', '')
                if magnet:
                    print(f"  Magnet: {magnet[:50]}...")
                else:
                    print("  Magnet: ❌ NOT AVAILABLE")
                
                # Print all available fields
                print("  Available fields:", list(result.keys()))
        
        return True
        
    except Exception as e:
        print(f"Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_magnet_links()
