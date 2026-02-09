"""Base parser class for Chrome-based web scraping."""

import os
import tempfile
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

try:
    from webdriver_manager.chrome import ChromeDriverManager
    WEBDRIVER_MANAGER_AVAILABLE = True
except ImportError:
    WEBDRIVER_MANAGER_AVAILABLE = False


class BaseChromeParser:
    """Base class for Chrome-based web scrapers."""
    
    def __init__(self, headless: bool = True, timeout: int = 30):
        self.headless = headless
        self.timeout = timeout
        self.driver = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.chrome_available = False
        
        # Try to setup driver, but don't fail if Chrome is not available
        try:
            self._setup_driver()
            self.chrome_available = True
        except Exception as e:
            self.logger.warning(f"Chrome WebDriver not available: {e}")
            self.chrome_available = False
    
    def _setup_driver(self):
        """Set up Chrome WebDriver with appropriate options."""
        try:
            chrome_options = Options()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            # Common Chrome options for server environments
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--no-first-run")
            chrome_options.add_argument("--disable-default-apps")
            chrome_options.add_argument("--disable-background-timer-throttling")
            chrome_options.add_argument("--disable-backgrounding-occluded-windows")
            chrome_options.add_argument("--disable-renderer-backgrounding")
            chrome_options.add_argument("--disable-infobars")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            # Set user agent
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Set Chrome binary path if available
            import os
            chrome_bin = os.environ.get('CHROME_BIN')
            if chrome_bin:
                chrome_options.binary_location = chrome_bin
            
            # Try to create WebDriver
            try:
                if WEBDRIVER_MANAGER_AVAILABLE:
                    # Use webdriver-manager for automatic driver management
                    service = Service(ChromeDriverManager().install())
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    # Try with system Chrome/Chromium first
                    self.driver = webdriver.Chrome(options=chrome_options)
            except WebDriverException as first_error:
                self.logger.warning(f"First attempt failed: {first_error}")
                # Fallback: try with explicit service
                try:
                    service = Service()
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                except WebDriverException as second_error:
                    self.logger.error(f"Second attempt failed: {second_error}")
                    # Final fallback: try to find chrome binary manually
                    try:
                        for chrome_path in ['/usr/bin/google-chrome-stable', '/usr/bin/google-chrome', '/usr/bin/chromium-browser']:
                            if os.path.exists(chrome_path):
                                chrome_options.binary_location = chrome_path
                                service = Service()
                                self.driver = webdriver.Chrome(service=service, options=chrome_options)
                                break
                        else:
                            raise RuntimeError(
                                "Chrome WebDriver could not be initialized. "
                                "Chrome binary not found or chromedriver incompatible."
                            )
                    except Exception as final_error:
                        self.logger.error(f"All attempts failed: {final_error}")
                        raise RuntimeError(
                            "Chrome WebDriver could not be initialized. "
                            "Please ensure Chrome/Chromium is installed and accessible."
                        )
            
            # Set implicit wait
            self.driver.implicitly_wait(10)
            
        except Exception as e:
            self.logger.error(f"Error setting up driver: {e}")
            raise
    
    def _cleanup(self):
        """Clean up the WebDriver instance."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                self.logger.warning(f"Error during driver cleanup: {e}")
            finally:
                self.driver = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()
    
    def __del__(self):
        self._cleanup()
    
    def wait_for_element(self, by, value, timeout=None):
        """Wait for an element to be present."""
        timeout = timeout or self.timeout
        return WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
    
    def wait_for_clickable(self, by, value, timeout=None):
        """Wait for an element to be clickable."""
        timeout = timeout or self.timeout
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )
    
    def get_page_content(self, url: str) -> str:
        """Get page content from URL."""
        self.driver.get(url)
        return self.driver.page_source
    
    def exists(self, name: str) -> bool:
        """Check if name exists in sanctions list. To be implemented by subclasses."""
        if not self.chrome_available:
            raise RuntimeError("Chrome WebDriver is not available in this environment")
        raise NotImplementedError("Subclasses must implement exists() method")
    
    def fetch(self, name: str) -> tuple:
        """
        Fetch sanctions data for a name.
        Returns tuple: (found: bool, content_bytes: bytes, filename: str, media_type: str)
        To be implemented by subclasses.
        """
        if not self.chrome_available:
            # Return a default response when Chrome is not available
            error_msg = f"Sanctions checking is currently unavailable (Chrome WebDriver not found). Please try again later."
            return (False, error_msg.encode('utf-8'), "error.txt", "text/plain")
        raise NotImplementedError("Subclasses must implement fetch() method")