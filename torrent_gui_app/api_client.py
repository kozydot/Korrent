"""
TorrentApi HTTP client for GraphQL endpoints
"""

import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime


class TorrentApiClient:
    """
    Client for communicating with TorrentApi GraphQL endpoint
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 30):
        """
        Initialize the API client
        
        Args:
            base_url: Base URL of the TorrentApi server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.graphql_endpoint = f"{self.base_url}/graphql"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        # Set timeout for all requests
        self.session.timeout = timeout
    
    def search(self, query: str, category: Optional[str] = None, 
               sort_by: Optional[str] = None, order: str = "desc", 
               providers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for torrents using GraphQL query
        
        Args:
            query: Search query string
            category: Category filter (All, Audio, Video, Applications, Games, Other)
            sort_by: Sort column (Seeders, Added, Size, Leechers)
            order: Sort order ("desc" or "asc")
            providers: List of provider names (PirateBay, YTS, BitSearch)
            
        Returns:
            List of torrent dictionaries
        """
        # Map category from Korrent format to TorrentApi format (GraphQL enums are UPPERCASE)
        category_mapping = {
            "Any": "ALL",
            "Movies/TV": "VIDEO",
            "Music": "AUDIO",
            "Games": "GAMES",
            "Apps": "APPLICATIONS",
            "Other": "OTHER"
        }
        
        # Map sort options from Korrent format to TorrentApi format (GraphQL enums are UPPERCASE)
        sort_mapping = {
            "time": "ADDED",
            "size": "SIZE", 
            "seeders": "SEEDERS",
            "leechers": "LEECHERS"
        }
        
        # Map order from Korrent format to TorrentApi format
        order_mapping = {
            "desc": "DESCENDING",
            "asc": "ASCENDING"
        }
        
        # Map providers from user-friendly names to API format
        provider_mapping = {
            "PirateBay": "PIRATEBAY",
            "YTS": "YTS", 
            "BitSearch": "BITSEARCH"
        }
        
        # Prepare GraphQL variables
        api_category = category_mapping.get(category, "ALL") if category else "ALL"
        api_sort = sort_mapping.get(sort_by, "SEEDERS") if sort_by else "SEEDERS"
        api_order = order_mapping.get(order, "DESCENDING")
        
        # Convert providers to API format, default to all if none specified
        if providers and len(providers) > 0:
            api_providers = [provider_mapping.get(p, p) for p in providers if p in provider_mapping]
            # If no valid providers after mapping, use all
            if not api_providers:
                api_providers = list(provider_mapping.values())
        else:
            api_providers = list(provider_mapping.values())  # Use all providers by default
        
        # Build GraphQL query with enum values as variables
        graphql_query = """
        query SearchTorrents($query: String!, $category: Category!, $sort: SortColumn!, $order: Order!, $limit: Int!, $providers: [Provider!]!) {
            searchTorrents(params: {
                query: $query,
                category: $category,
                sort: $sort,
                order: $order,
                limit: $limit,
                providers: $providers
            }) {
                torrents {
                    added
                    category
                    fileCount
                    id
                    infoHash
                    leechers
                    name
                    seeders
                    size
                    magnet
                    provider
                }
                errors {
                    provider
                    error
                }
            }
        }
        """
        
        variables = {
            "query": query,
            "category": api_category,
            "sort": api_sort,
            "order": api_order,
            "providers": api_providers,
            "limit": 100  # Reasonable limit for GUI display
        }
        
        try:
            response = self.session.post(
                self.graphql_endpoint,
                json={
                    "query": graphql_query,
                    "variables": variables
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check for GraphQL errors
            if "errors" in data:
                raise Exception(f"GraphQL errors: {data['errors']}")
            
            # Extract torrents from response
            search_result = data.get("data", {}).get("searchTorrents", {})
            torrents = search_result.get("torrents", [])
            errors = search_result.get("errors", [])
            
            # Log provider errors if any
            if errors:
                error_msgs = []
                for error in errors:
                    provider = error.get("provider", "Unknown")
                    error_msg = error.get("error", "Unknown error")
                    error_msgs.append(f"{provider}: {error_msg}")
                
                # If we have some results but also errors, just log them
                if torrents:
                    print(f"Warning: Some providers failed: {'; '.join(error_msgs)}")
                else:
                    # If no results and there are errors, raise them
                    raise Exception(f"All providers failed: {'; '.join(error_msgs)}")
            
            # Convert to format expected by Korrent
            return [self._convert_torrent(t) for t in torrents]
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            raise Exception(f"Search failed: {str(e)}")
    
    def get_torrent_details(self, torrent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific torrent
        
        Since TorrentApi returns full details in search results,
        we'll return a formatted details object based on the ID
        
        Args:
            torrent_id: The torrent info hash
            
        Returns:
            Torrent details dictionary or None
        """
        # For now, we'll need to store torrent details from search results
        # or make another search query. In a real implementation, you might
        # want to cache search results or have a separate details endpoint.
        
        # Return None to indicate we need to use cached data from search
        return None
    
    def _convert_torrent(self, torrent: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert TorrentApi torrent format to Korrent format
        
        Args:
            torrent: Torrent data from API
            
        Returns:
            Formatted torrent dictionary
        """
        # Parse the ISO timestamp
        try:
            added_dt = datetime.fromisoformat(torrent.get("added", "").replace("Z", "+00:00"))
            time_str = added_dt.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = "Unknown"
        
        # Format size to human readable
        size_bytes = torrent.get("size", 0)
        size_str = self._format_size(size_bytes)
        
        # Get seeders and leechers
        seeders = torrent.get("seeders", 0)
        leechers = torrent.get("leechers", 0)
        
        # Get provider and convert from list if needed
        provider = torrent.get("provider", "Unknown")
        if isinstance(provider, list):
            provider = provider[0] if provider else "Unknown"
        
        # Build the torrent item in Korrent format
        return {
            "name": torrent.get("name", "Unknown"),
            "size": size_str,
            "time": time_str,
            "seeders": str(seeders),
            "leechers": str(leechers),
            "torrent_id": torrent.get("infoHash", ""),  # Use info hash as ID
            "magnet_link": torrent.get("magnet", ""),
            "category": torrent.get("category", "Other"),
            "provider": provider,  # Include provider info
            "uploader": "TorrentApi",  # No uploader info in API
            "url": f"/torrent/{torrent.get('infoHash', '')}"  # Fake URL for compatibility
        }
    
    def _format_size(self, size_bytes: int) -> str:
        """
        Format bytes to human readable size
        
        Args:
            size_bytes: Size in bytes
            
        Returns:
            Formatted size string
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to the TorrentApi server
        
        Returns:
            Dictionary with connection status and any error messages
        """
        try:
            # Simple GraphQL introspection query to test connectivity
            test_query = """
            query {
                __schema {
                    types {
                        name
                    }
                }
            }
            """
            
            response = self.session.post(
                self.graphql_endpoint,
                json={"query": test_query},
                timeout=10  # Shorter timeout for connection test
            )
            
            if response.status_code == 200:
                return {
                    "status": "success",
                    "message": "Successfully connected to TorrentApi server",
                    "url": self.base_url
                }
            else:
                return {
                    "status": "error",
                    "message": f"Server returned status {response.status_code}",
                    "url": self.base_url
                }
                
        except requests.exceptions.ConnectTimeout:
            return {
                "status": "error",
                "message": "Connection timeout - server may be down or unreachable",
                "url": self.base_url
            }
        except requests.exceptions.ConnectionError as e:
            return {
                "status": "error", 
                "message": f"Connection error: {str(e)}",
                "url": self.base_url
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"Network error: {str(e)}",
                "url": self.base_url
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}",
                "url": self.base_url
            }

class TorrentInfo:
    """
    Wrapper class for torrent information with convenient access methods
    """
    
    def __init__(self, data: Dict[str, Any]):
        """
        Initialize TorrentInfo from torrent data dictionary
        
        Args:
            data: Dictionary containing torrent information
        """
        self.data = data
        self.torrent_id = data.get("torrent_id", data.get("infoHash", data.get("id", "")))
        self.name = data.get("name", "Unknown")
        self.size = data.get("size", "Unknown")
        self.category = data.get("category", "Unknown")
        self.provider = data.get("provider", "Unknown") 
        self.magnet_link = data.get("magnet_link", data.get("magnet", ""))
        self.seeders = data.get("seeders", "0")
        self.leechers = data.get("leechers", "0")
        self.date_added = data.get("added", data.get("time", "Unknown"))
        self.file_count = data.get("fileCount", 1)
        
        # Additional properties for compatibility
        self.uploader = data.get("uploader", "Unknown")
        self.uploader_link = data.get("uploader_link", None)
        self.downloads = data.get("downloads", "N/A")
        self.last_checked = data.get("last_checked", "Recently")
        self.date_uploaded = self.date_added
        self.info_hash = self.torrent_id
        self.type = data.get("type", "Unknown")
        self.language = data.get("language", "Unknown")
        self.description = data.get("description", "No description available.")

    def get(self, key: str, default=None):
        """Get value from underlying data dictionary"""
        return self.data.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return self.data.copy()