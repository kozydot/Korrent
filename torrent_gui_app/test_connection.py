#!/usr/bin/env python3
"""
Quick test script to verify the TorrentApi connection and search functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_client import TorrentApiClient

def test_connection():
    """Test connection to TorrentApi server"""
    print("Testing connection to TorrentApi server...")
    
    client = TorrentApiClient(base_url="http://localhost:8000", timeout=10)
    result = client.test_connection()
    
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    print(f"URL: {result['url']}")
    
    return result['status'] == 'success'

def test_search():
    """Test search functionality with different providers"""
    print("\nTesting search functionality...")
    
    client = TorrentApiClient(base_url="http://localhost:8000", timeout=30)
    
    # Test with all providers
    try:
        print("Searching for 'avengers' with all providers...")
        results = client.search("avengers", providers=["PirateBay", "YTS", "BitSearch"])
        print(f"Found {len(results)} results")
        
        if results:
            print("Sample result:")
            sample = results[0]
            print(f"  Name: {sample.get('name', 'Unknown')}")
            print(f"  Size: {sample.get('size', 'Unknown')}")
            print(f"  Seeders: {sample.get('seeders', 'Unknown')}")
            print(f"  Provider: {sample.get('provider', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"Search failed: {str(e)}")
        return False

def test_individual_providers():
    """Test each provider individually"""
    print("\nTesting individual providers...")
    
    client = TorrentApiClient(base_url="http://localhost:8000", timeout=30)
    providers = ["PirateBay", "YTS", "BitSearch"]
    
    for provider in providers:
        try:
            print(f"\nTesting {provider}...")
            results = client.search("movie", providers=[provider])
            print(f"  {provider}: Found {len(results)} results")
            
        except Exception as e:
            print(f"  {provider}: Failed - {str(e)}")

if __name__ == "__main__":
    success = True
    
    # Test connection
    if not test_connection():
        print("❌ Connection test failed!")
        success = False
    else:
        print("✅ Connection test passed!")
    
    # Test search
    if not test_search():
        print("❌ Search test failed!")
        success = False
    else:
        print("✅ Search test passed!")
    
    # Test individual providers
    test_individual_providers()
    
    if success:
        print("\n✅ All basic tests passed!")
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)
