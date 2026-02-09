"""
Alternative implementations for sanctions parsers that work without browser automation.
These are API-based alternatives that can run in cloud environments.
"""

import requests
import logging
from typing import Tuple, Optional
import json


class APIBasedSanctionsEU:
    """EU sanctions parser using API calls instead of browser automation."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
    
    def fetch(self, name: str) -> Tuple[bool, bytes, str, str]:
        """
        Fetch EU sanctions data via API.
        Returns tuple: (found: bool, content_bytes: bytes, filename: str, media_type: str)
        """
        try:
            # For now, return a message that the service requires browser automation
            message = {
                "status": "unavailable",
                "message": "EU sanctions checking requires browser automation which is not available in this environment.",
                "searched_name": name,
                "suggestion": "Please check manually at https://www.sanctionsmap.eu/"
            }
            content = json.dumps(message, indent=2, ensure_ascii=False)
            return (False, content.encode('utf-8'), f"eu_sanctions_unavailable_{name}.json", "application/json")
            
        except Exception as e:
            self.logger.error(f"Error in EU sanctions API: {e}")
            error_msg = f"Error checking EU sanctions for '{name}': {str(e)}"
            return (False, error_msg.encode('utf-8'), "error.txt", "text/plain")


class APIBasedSanctionsOFAC:
    """OFAC sanctions parser using API calls instead of browser automation."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
    
    def fetch(self, name: str) -> Tuple[bool, bytes, str, str]:
        """
        Fetch OFAC sanctions data via API.
        Returns tuple: (found: bool, content_bytes: bytes, filename: str, media_type: str)
        """
        try:
            # For now, return a message that the service requires browser automation
            message = {
                "status": "unavailable", 
                "message": "OFAC sanctions checking requires browser automation which is not available in this environment.",
                "searched_name": name,
                "suggestion": "Please check manually at https://sanctionssearch.ofac.treas.gov"
            }
            content = json.dumps(message, indent=2, ensure_ascii=False)
            return (False, content.encode('utf-8'), f"ofac_sanctions_unavailable_{name}.json", "application/json")
            
        except Exception as e:
            self.logger.error(f"Error in OFAC sanctions API: {e}")
            error_msg = f"Error checking OFAC sanctions for '{name}': {str(e)}"
            return (False, error_msg.encode('utf-8'), "error.txt", "text/plain")


class APIBasedSanctionsUN:
    """UN sanctions parser using direct HTTP requests."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        self.base_url = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"
    
    def fetch(self, name: str) -> Tuple[bool, bytes, str, str]:
        """
        Fetch UN sanctions data via direct HTTP requests.
        Returns tuple: (found: bool, content_bytes: bytes, filename: str, media_type: str)
        """
        try:
            # Try to get the UN consolidated list directly
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
            
            # For now, return the page content and let user search manually
            # In the future, we could parse this more intelligently
            found = name.lower() in response.text.lower()
            
            result = {
                "status": "partial_check",
                "found": found,
                "searched_name": name,
                "message": f"Basic text search {'found' if found else 'did not find'} the name '{name}' in UN sanctions list.",
                "note": "This is a simple text search. For detailed verification, please check manually.",
                "url": self.base_url
            }
            
            content = json.dumps(result, indent=2, ensure_ascii=False)
            filename = f"un_sanctions_check_{name}.json"
            
            return (found, content.encode('utf-8'), filename, "application/json")
            
        except Exception as e:
            self.logger.error(f"Error in UN sanctions API: {e}")
            error_msg = f"Error checking UN sanctions for '{name}': {str(e)}"
            return (False, error_msg.encode('utf-8'), "error.txt", "text/plain")