"""
Custom 1337x module with additional functionality and domain options
"""

import time
import random
from typing import Dict, List, Literal, Optional, Any

import cloudscraper
from bs4 import BeautifulSoup

from py1337x import utils, parser, models

# Updated list of alternative domains for 1337x - prioritizing most reliable ones
ALTERNATIVE_DOMAINS = [
    "https://1337x.unblockit.kim",  # Unblock service that provides access
    "https://1337x.unblockninja.com",  # Another unblock service
    "https://1337x.to",
    "https://1337x.proxyninja.org",
    "https://1337x.is",
    "https://1337x.st",
    "https://x1337x.ws",
    "https://x1337x.eu",
    "https://x1337x.se",
    "https://x1337x.cc",
    "https://1337.abcvg.info"
]

class Custom1337x:
    """
    Enhanced version of py1337x.Py1337x with better error handling
    and domain rotation to bypass cloudflare protection.
    """
    def __init__(
        self,
        base_url: str = "",
    ):
        """
        Initialize with a random domain from the list of alternatives if none provided
        """
        # Use provided base_url or select a random one from alternatives
        if not base_url:
            base_url = random.choice(ALTERNATIVE_DOMAINS)
            
        # Setup browser configuration for cloudscraper
        browser_config = {
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
            
        # Initialize the scraper
        self.scraper = cloudscraper.create_scraper(browser=browser_config)
        self.base_url = base_url
        self.url_builder = utils.URLBuilder(base_url)
        
        # Store our list of domains
        self.domains = ALTERNATIVE_DOMAINS
        self.current_domain_index = self.domains.index(base_url) if base_url in self.domains else 0
        self.max_retries = len(self.domains)  # Try all domains before giving up

    def _rotate_domain(self):
        """Rotate to the next domain in the list"""
        self.current_domain_index = (self.current_domain_index + 1) % len(self.domains)
        self.base_url = self.domains[self.current_domain_index]
        self.url_builder = utils.URLBuilder(self.base_url)
        # Re-create the scraper to reset any cookies/session data
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )
        print(f"Switched to alternative domain: {self.base_url}")

    def search(
        self,
        query: str,
        page: int = 1,
        category: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: str = "desc",
    ):
        """
        Enhanced search with domain rotation on failure
        """
        query = self.url_builder.sanitize_query(query)
        category = self.url_builder.sanitize_category(category)
        
        attempts = 0
        
        while attempts < self.max_retries:
            try:
                # Build the search URL
                url = self.url_builder.build_search_url(query, page, category, sort_by, order)
                print(f"Trying to search from: {url}")
                
                # Make the request
                response = self.scraper.get(url)
                
                if response.status_code == 200:
                    # Check if we have any results content
                    soup = BeautifulSoup(response.content, "html.parser")
                    
                    # If we found search results
                    if soup.select('a[href*="/torrent/"]'):
                        result = parser.torrent_parser(response, base_url=self.base_url, page=page)
                        if result.items:
                            return result
                    
                    print(f"No search results found on {self.base_url}. Rotating domain...")
                else:
                    print(f"Invalid response from {self.base_url}. Rotating domain...")
            except Exception as e:
                print(f"Error searching on {self.base_url}: {e}")
            
            # If we get here, the request failed or had no results
            self._rotate_domain()
            attempts += 1
            # Add a small delay between retries
            time.sleep(1)
        
        # If all domains failed, return empty results
        print("All domains failed to return search results.")
        return models.TorrentResult(items=[], current_page=page, item_count=0, page_count=1)

    def info(self, link: Optional[str] = None, torrent_id: Optional[str] = None):
        """
        Enhanced info retrieval with domain rotation on failure
        """
        attempts = 0
        
        while attempts < self.max_retries:
            try:
                # Build the info URL - verify we have valid inputs
                if link is None and torrent_id is None:
                    raise ValueError("Either link or torrent_id must be provided")
                
                # Ensure we're passing valid URL to the scraper
                url = self.url_builder.build_info_url(link, torrent_id)
                if not url:
                    raise ValueError("Invalid URL generated")
                    
                print(f"Trying to fetch details from: {url}")
                
                # Make the request
                response = self.scraper.get(url)
                
                if response.status_code == 200:
                    # Parse the response content
                    soup = BeautifulSoup(response.content, "html.parser")
                    
                    # Check if we have any content
                    box_info = soup.find("div", {"class": "box-info-heading"})
                    if not box_info:
                        print(f"Got response from {self.base_url} but no torrent details found. Rotating domain...")
                        self._rotate_domain()
                        attempts += 1
                        continue
                    
                    # If we have content, try to parse it
                    try:
                        result = parser.info_parser(response, base_url=self.base_url)
                        
                        # Check if the parsed result has essential fields
                        if result.magnet_link:
                            # Store torrent_id as metadata with the result for future reference
                            if torrent_id:
                                # Use setattr to add torrent_id dynamically, avoiding the attribute error
                                setattr(result, 'torrent_id', torrent_id)
                            return result
                    except Exception as e:
                        print(f"Failed to parse details: {e}")
                
                # If we get here, either the response wasn't 200 or parsing failed
                print(f"Invalid response from {self.base_url}. Rotating domain...")
            except Exception as e:
                print(f"Error accessing {self.base_url} for details: {e}")
            
            # If we get here, the request failed
            self._rotate_domain()
            attempts += 1
            # Add a small delay between retries
            time.sleep(1)
        
        # If all domains failed, create a minimal info object
        print("All domains failed to retrieve details. Creating minimal info object.")
        
        # Create a minimal TorrentInfo object
        minimal_info = models.TorrentInfo(
            name="Unable to retrieve details",
            short_name=None,
            description="Torrent details could not be retrieved from any available domains.",
            category=None,
            type=None,
            genre=None,
            language=None,
            size=None,
            thumbnail=None,
            images=None,
            uploader=None,
            uploader_link=None,
            downloads=None,
            last_checked=None,
            date_uploaded=None,
            seeders=None,
            leechers=None,
            magnet_link=None,
            info_hash=None,
        )
        
        # Add torrent_id if available, using setattr to avoid attribute error
        if torrent_id:
            setattr(minimal_info, 'torrent_id', torrent_id)
            
        return minimal_info 