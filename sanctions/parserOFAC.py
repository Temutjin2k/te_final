import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from .base_parser import BaseChromeParser


class ParserOFAC(BaseChromeParser):
    URL = "https://sanctionssearch.ofac.treas.gov"

    def __init__(self, timeout: int = 20):
        super().__init__()
        self.timeout = timeout

    def _wait(self, cond):
        return WebDriverWait(self.driver, self.timeout).until(cond)

    def exists(self, name: str) -> bool:
        try:
            self.driver.get(self.URL)
            tbl = self._wait(EC.visibility_of_element_located((By.CLASS_NAME, "MainTable")))
            box = tbl.find_element(By.ID, "ctl00_MainContent_txtLastName")
            box.clear(); box.send_keys(name); box.send_keys(Keys.ENTER)
            try:
                self._wait(EC.presence_of_element_located((By.ID, "gvSearchResults")))
            except TimeoutException:
                return False
            rows = self.driver.find_element(By.ID, "gvSearchResults").find_elements(By.CSS_SELECTOR, "tr")
            return any(r.find_elements(By.TAG_NAME, "a") for r in rows)
        finally:
            self._cleanup()

    def fetch(self, name: str):
        if not self.chrome_available or self.driver is None:
            # Return API-based fallback response
            import json
            message = {
                "status": "unavailable",
                "message": "OFAC sanctions checking requires browser automation which is not available in this environment.",
                "searched_name": name,
                "suggestion": "Please check manually at https://sanctionssearch.ofac.treas.gov"
            }
            content = json.dumps(message, indent=2, ensure_ascii=False)
            return (False, content.encode('utf-8'), f"ofac_sanctions_unavailable_{name}.json", "application/json")
            
        try:
            self.driver.get(self.URL)
            tbl = self._wait(EC.visibility_of_element_located((By.CLASS_NAME, "MainTable")))
            box = tbl.find_element(By.ID, "ctl00_MainContent_txtLastName")
            box.clear(); box.send_keys(name); box.send_keys(Keys.ENTER)
            try:
                self._wait(EC.presence_of_element_located((By.ID, "gvSearchResults")))
            except TimeoutException:
                png = self.driver.get_screenshot_as_png()
                return False, png, f"{name}_ofac.png", "image/png"
            table = self.driver.find_element(By.ID, "gvSearchResults")
            link = None
            for row in table.find_elements(By.CSS_SELECTOR, "tr"):
                links = row.find_elements(By.TAG_NAME, "a")
                if links:
                    link = links[0]
                    break
            if not link:
                png = self.driver.get_screenshot_as_png()
                return False, png, f"{name}_ofac_not_found.png", "image/png"
            prev_handles = set(self.driver.window_handles)
            link.click()
            time.sleep(0.5)
            new_handles = [h for h in self.driver.window_handles if h not in prev_handles]
            if new_handles:
                self.driver.switch_to.window(new_handles[0])
            try:
                self._wait(EC.presence_of_element_located((By.CLASS_NAME, "MainTable")))
            except TimeoutException:
                pass
            png = self.driver.get_screenshot_as_png()
            return True, png, f"{name}_ofac.png", "image/png"

        except (TimeoutException, NoSuchElementException):
            png = self.driver.get_screenshot_as_png()
            return False, png, f"{name}_ofac.png", "image/png"
        finally:
            self._cleanup()
