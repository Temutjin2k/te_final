import requests
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from .base_parser import BaseChromeParser


class ParserUN(BaseChromeParser):
    def __init__(self):
        super().__init__()
        self.url = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"

    def exists(self, name: str) -> bool:
        try:
            self.driver.get(self.url)
            self.driver.implicitly_wait(5)
            link_to_html = self.driver.find_element(By.CLASS_NAME, "field__items").find_elements(By.TAG_NAME,"p")[1].find_elements(By.TAG_NAME,"a")[-1].get_attribute('href')
            response = requests.get(link_to_html)
            if response.status_code != 200:
                return False
            return self._found_near_name_label(name, response.text)
        except Exception:
            return False
        finally:
            self._cleanup()

    def fetch(self, name: str):
        """Return tuple: (found: bool, content_bytes: bytes, filename: str, media_type: str)
        - Always returns the HTML list file as bytes so it can be downloaded
        - "found" is computed by checking if the provided name appears near a "NAME:" label
        """
        if not self.chrome_available or self.driver is None:
            # Try direct HTTP request as fallback
            try:
                response = requests.get("https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list", timeout=30)
                response.raise_for_status()
                
                # Simple text search
                found = name.lower() in response.text.lower()
                
                import json
                result = {
                    "status": "partial_check",
                    "found": found,
                    "searched_name": name,
                    "message": f"Basic text search {'found' if found else 'did not find'} the name '{name}' in UN sanctions list.",
                    "note": "This is a simple text search. For detailed verification, please check manually.",
                    "url": "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"
                }
                
                content = json.dumps(result, indent=2, ensure_ascii=False)
                return (found, content.encode('utf-8'), f"un_sanctions_check_{name}.json", "application/json")
                
            except Exception as e:
                error_msg = f"Error checking UN sanctions for '{name}': {str(e)}"
                return (False, error_msg.encode('utf-8'), "error.txt", "text/plain")
        
        try:
            self.driver.get(self.url)
            self.driver.implicitly_wait(5)
            link_to_html = self.driver.find_element(By.CLASS_NAME, "field__items").find_elements(By.TAG_NAME,"p")[1].find_elements(By.TAG_NAME,"a")[-1].get_attribute('href')
            response = requests.get(link_to_html)
            ok = response.status_code == 200
            content_text = response.text if ok else ""
            found = self._found_near_name_label(name, content_text) if ok else False
            filename = f"{name}_un.html"
            return found, (content_text.encode("utf-8") if ok else b""), filename, "text/html"
        finally:
            self._cleanup()

    def _found_near_name_label(self, name: str, html: str) -> bool:
        """Check if all tokens of the name appear within a short window after a 'NAME:' label."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=' ').lower()
        except Exception:
            text = html.lower()

        target = name.lower().strip()
        if not target:
            return False
        idx = text.find('name:')
        while idx != -1:
            window = text[idx: idx + 200]
            if all(part in window for part in target.split()):
                return True
            idx = text.find('name:', idx + 5)
        return False