import time
import base64
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from .base_parser import BaseChromeParser


class SanctionsEU(BaseChromeParser):
    def __init__(self):
        super().__init__()
        self.url = "https://www.sanctionsmap.eu/#/main"

    def exists(self, name: str) -> bool:
        try:
            self.driver.get(self.url)
            self.driver.implicitly_wait(5)
            WebDriverWait(self.driver, 15).until(EC.visibility_of_element_located((By.ID, "search-box-input")))
            time.sleep(2)
            self._findName(name)
            return True
        except NoSuchElementException:
            try:
                search_input = WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.ID, "search-box-input")))
                search_input.send_keys(Keys.ENTER)
            except Exception:
                pass
            return False
        finally:
            self._cleanup()

    def fetch(self, name: str):
        """Return tuple: (found: bool, content_bytes: bytes, filename: str, media_type: str)"""
        try:
            self.driver.get(self.url)
            self.driver.implicitly_wait(5)
            try:
                search_input = WebDriverWait(self.driver,30).until(EC.visibility_of_element_located((By.ID, "search-box-input")))
            except TimeoutException:
                screenshot_bytes = self.driver.get_screenshot_as_png()
                return False, screenshot_bytes, f"{name}_eu.png", "image/png"
            time.sleep(2)
            try:
                self._findName(name)
                content = self._downloadList()
                return True, content, f"{name}_eu.png", "image/png"
            except NoSuchElementException:
                search_input.send_keys(Keys.ENTER)
                time.sleep(1)
                screenshot_bytes = self.driver.get_screenshot_as_png()
                return False, screenshot_bytes, f"{name}_eu.png", "image/png"
        finally:
            self._cleanup()

    def _generate_name_variants(self, name: str) -> list:
        """Генерирует варианты названия с разным порядком ОПФ"""
        variants = [name]  # Оригинальное название
        
        # Список организационно-правовых форм
        legal_forms = [
            r'\bJSC\b', r'\bPJSC\b', r'\bOJSC\b', r'\bCJSC\b',
            r'\bLLC\b', r'\bLTD\b', r'\bLimited\b',
            r'\bPLC\b', r'\bInc\b', r'\bCorp\b', r'\bCorporation\b',
            r'\bGmbH\b', r'\bAG\b', r'\bSA\b', r'\bSARL\b',
            r'\bAO\b', r'\bOOO\b', r'\bZAO\b', r'\bPAO\b'
        ]
        
        # Ищем ОПФ в начале или конце названия
        for form_pattern in legal_forms:
            # Если ОПФ в начале - пробуем переместить в конец
            match = re.match(f'^({form_pattern})\\s+(.+)', name, re.IGNORECASE)
            if match:
                legal_form = match.group(1)
                company_name = match.group(2)
                variants.append(f"{company_name} {legal_form}")
                variants.append(company_name)  # Без ОПФ
                break
            
            # Если ОПФ в конце - пробуем переместить в начало
            match = re.search(f'(.+)\\s+({form_pattern})$', name, re.IGNORECASE)
            if match:
                company_name = match.group(1)
                legal_form = match.group(2)
                variants.append(f"{legal_form} {company_name}")
                variants.append(company_name)  # Без ОПФ
                break
        
        return variants
    
    def _findName(self, name: str):
        """Ищет название, пробуя разные варианты"""
        search_input = WebDriverWait(self.driver, 15).until(
            EC.visibility_of_element_located((By.ID, "search-box-input"))
        )
        
        # Генерируем варианты названия
        name_variants = self._generate_name_variants(name)
        
        # Пробуем каждый вариант
        for attempt, variant in enumerate(name_variants):
            try:
                # Очищаем поле поиска перед новой попыткой
                if attempt > 0:
                    search_input.clear()
                    time.sleep(0.5)
                
                search_input.send_keys(variant)
                time.sleep(2)
                
                # Пытаемся найти dropdown с результатами
                typeahead = self.driver.find_element(By.TAG_NAME, "ngb-typeahead-window")
                persons = typeahead.find_elements(By.CLASS_NAME, "dropdown-item")
                
                if persons:
                    persons[0].click()
                    return  # Успешно нашли и кликнули
                    
            except NoSuchElementException:
                # Dropdown не появился, пробуем следующий вариант
                if attempt < len(name_variants) - 1:
                    continue
                else:
                    # Это была последняя попытка
                    raise
        
        # Если дошли сюда, ничего не нашли
        raise NoSuchElementException(f"Name not found: tried variants {name_variants}")

    def _downloadList(self):
        time.sleep(2)
        page_filter = self.driver.find_element(By.CLASS_NAME, "filter-list").find_element(By.CSS_SELECTOR, '[data-heading="List"]').find_element(By.TAG_NAME, "a")
        page_filter.click()
        self.driver.implicitly_wait(5)
        time.sleep(1)
        return self._capture_full_page_png()

    def _capture_full_page_png(self):
        try:
            self.driver.execute_cdp_cmd("Page.enable", {})
        except Exception:
            pass
        metrics = self.driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
        content_size = metrics.get("contentSize", {})
        width = int(content_size.get("width", 1280))
        height = int(content_size.get("height", 1024))
        self.driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "mobile": False,
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "screenWidth": width,
            "screenHeight": height
        })
        screenshot_obj = self.driver.execute_cdp_cmd("Page.captureScreenshot", {
            "fromSurface": True,
            "captureBeyondViewport": True
        })
        return base64.b64decode(screenshot_obj.get("data", ""))
