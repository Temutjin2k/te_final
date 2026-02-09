import math
import time
import unicodedata
import logging
from typing import Tuple, List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter, Retry
from rapidfuzz import process, fuzz

try:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False


class ParserUK:
    BASE = "https://search-uk-sanctions-list.service.gov.uk"
    SEARCH_API = f"{BASE}/api/search/designations-open-search"
    REPORT_FINDING_API = f"{BASE}/api/report/sdf"
    REPORT_NOT_FOUND_API = f"{BASE}/api/report/ods"
    PAGE_URL_FMT = f"{BASE}/designations/{{unique_id}}/{{dtype}}"

    def __init__(self, page_size: int = 200, min_score: int = 80,
                 use_selenium_for_pagecount: bool = False, max_workers: int = 5, 
                 logger: Optional[logging.Logger] = None):
        self.page_size = page_size
        self.min_score = min_score
        self.use_selenium_for_pagecount = use_selenium_for_pagecount and SELENIUM_AVAILABLE
        self.max_workers = max_workers
        self.logger = logger or logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.session = self._build_session()

    def exists(self, name: str) -> bool:
        return self._search_and_maybe_download(name, download=False)[0]

    def fetch(self, name: str) -> Tuple[bool, bytes, str, str]:
        return self._search_and_maybe_download(name, download=True)

    def _search_and_maybe_download(self, name: str, download: bool):
        search_start_time = time.time()
        self.logger.info(f"[UK] Starting search for: {name!r}")
        
        first_payload = self._build_payload(name, page=1, current_page_no=0, item_from=1, item_to=self.page_size)
        first = self._post_json(self.SEARCH_API, first_payload)
        
        items, total = self._extract_data(first)
        
        if total is None or total < 0:
            self.logger.warning("[UK] API didn't return total; using Selenium to read pagecount" if self.use_selenium_for_pagecount else "[UK] API total missing; will assume single page")
            pages = self._read_max_pages_via_selenium(name) if self.use_selenium_for_pagecount else 1
        else:
            pages = math.ceil(total / self.page_size)

        self.logger.info(f"[UK] Search parameters: total_records≈{total}, page_size={self.page_size}, total_pages={pages}")
        self.logger.info(f"[UK] Will process {pages} pages in parallel to find matches for: {name!r}")

        all_rows = items[:]
        
        if pages > 1:
            with ThreadPoolExecutor(max_workers=min(pages-1, self.max_workers)) as executor:
                future_to_page = {executor.submit(self._process_page, name, p): p for p in range(2, pages + 1)}
                
                for future in as_completed(future_to_page):
                    page = future_to_page[future]
                    try:
                        page_items = future.result()
                        all_rows.extend(page_items)
                        self.logger.debug(f"[UK] Completed page {page}/{pages}")
                    except Exception as e:
                        self.logger.error(f"[UK] Error processing page {page}: {e}")

        search_time = time.time() - search_start_time
        self.logger.info(f"[UK] Search completed: collected {len(all_rows)} total records from {pages} pages in {search_time:.2f}s")
        self.logger.info(f"[UK] Starting fuzzy matching for: {name!r}")

        best = self._match_name(name, all_rows)
        if not best:
            self.logger.info("[UK] no fuzzy matches above threshold; downloading NOT FOUND report")
            if not download:
                total_time = time.time() - search_start_time
                self.logger.info(f"[UK] Search completed in {total_time:.2f}s (no matches, no download)")
                return False, b"", "", ""
            
            download_start_time = time.time()
            result = self._download_report(name)
            download_time = time.time() - download_start_time
            total_time = time.time() - search_start_time
            
            self.logger.info(f"[UK] NOT FOUND report downloaded in {download_time:.2f}s")
            self.logger.info(f"[UK] Total operation completed in {total_time:.2f}s")
            
            return False, *result

        row, score, idx = best
        unique_id = (row.get("documentKey") or row.get("unique_ID") or row.get("uniqueId") or "").strip()
        dtype = (row.get("entityType") or row.get("type") or "").strip().replace(" ", "")
        page_url = self.PAGE_URL_FMT.format(unique_id=unique_id, dtype=dtype or "Individual")
        self.logger.info(f"[UK] MATCH {score}% -> {self._row_name(row)} | id={unique_id} type={dtype} | {page_url}")

        if not download:
            total_time = time.time() - search_start_time
            self.logger.info(f"[UK] Search completed in {total_time:.2f}s (no download)")
            return True, b"", "", ""

        download_start_time = time.time()
        result = self._download_report(name, unique_id)
        download_time = time.time() - download_start_time
        total_time = time.time() - search_start_time
        
        self.logger.info(f"[UK] Download completed in {download_time:.2f}s")
        self.logger.info(f"[UK] Total operation completed in {total_time:.2f}s")
        
        return True, *result

    def _build_session(self):
        session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _build_payload(self, name: str, page: int, current_page_no: int, item_from: int, item_to: int) -> Dict[str, Any]:
        return {
            "searchValue": name,
            "regimeName": None,
            "designationSource": None,
            "designationType": None,
            "sanctionImposed": None,
            "dateFrom": None,
            "dateTo": None,
            "uniqueId": None,
            "isFuzzySearch": False,
            "isExactMatch": False,
            "currentPageNo": current_page_no,
            "itemFrom": item_from,
            "itemTo": item_to,
            "page": page,
            "pageSize": self.page_size,
        }

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self.session.post(url, json=payload, timeout=60)
        if not r.ok:
            raise RuntimeError(f"POST {url} failed: {r.status_code} {r.text[:200]}")
        return r.json()

    def _extract_data(self, page_json: Dict[str, Any], fallback: int = 0) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        self.logger.debug(f"[UK] Extracting data from: {type(page_json)} with keys: {list(page_json.keys()) if isinstance(page_json, dict) else 'N/A'}")
        
        items = []
        if isinstance(page_json, list):
            self.logger.debug(f"[UK] Direct list with {len(page_json)} items")
            items = page_json
        elif isinstance(page_json, dict) and isinstance(page_json.get("hits"), list):
            # OpenSearch-backed response shape: { totalCount, hits: [{ source, highlight, score }, ...] }
            hits = page_json.get("hits") or []
            extracted = []
            for h in hits:
                if isinstance(h, dict):
                    src = h.get("source")
                    if isinstance(src, dict):
                        extracted.append(src)
            items = extracted
        else:
            for key in ("data", "rows", "results", "items"):
                if isinstance(page_json.get(key), list):
                    self.logger.debug(f"[UK] Found items under key '{key}' with {len(page_json[key])} items")
                    items = page_json[key]
                    break
            else:
                for k, v in page_json.items():
                    if isinstance(v, list) and v and isinstance(v[0], dict) and "name" in v[0]:
                        self.logger.debug(f"[UK] Found items under key '{k}' with {len(v)} items")
                        items = v
                        break
                else:
                    if isinstance(page_json, dict) and "name" in page_json:
                        self.logger.debug("[UK] Single record found")
                        items = [page_json]
        
        if not items:
            self.logger.warning(f"[UK] No items found in response: {page_json}")
            return [], fallback
        
        total = None
        if isinstance(page_json, list) and page_json:
            v = page_json[0].get("numberOfRows") if isinstance(page_json[0], dict) else None
            if isinstance(v, int):
                total = v
            elif isinstance(v, str):
                try:
                    total = int(v.replace(",", ""))
                except Exception:
                    pass
        elif isinstance(page_json, dict):
            v = page_json.get("totalCount")
            if isinstance(v, int):
                total = v
            for key in ("total", "recordsTotal", "recordsFiltered", "count"):
                v = page_json.get(key)
                if isinstance(v, int):
                    total = v
                    break
                elif isinstance(v, str) and v.isdigit():
                    total = int(v)
                    break
        
        if total is None and items:
            v = items[0].get("numberOfRows") if isinstance(items[0], dict) else None
            if isinstance(v, int):
                total = v
            elif isinstance(v, str):
                try:
                    total = int(v.replace(",", ""))
                except Exception:
                    pass
        
        return items, total or fallback

    def _process_page(self, name: str, page: int) -> List[Dict[str, Any]]:
        """Обрабатывает одну страницу и возвращает элементы"""
        payload = self._build_payload(name, page=page, current_page_no=page-1, 
                                    item_from=(page-1) * self.page_size + 1, item_to=page * self.page_size)
        page_json = self._post_json(self.SEARCH_API, payload)
        page_items, _ = self._extract_data(page_json)
        self.logger.debug(f"[UK] Processed page {page}: {len(page_items)} items")
        return page_items

    def _read_max_pages_via_selenium(self, name: str) -> int:
        if not self.use_selenium_for_pagecount or not SELENIUM_AVAILABLE:
            return 1
            
        self.logger.info(f"[UK] Using Selenium to read page count for: {name!r}")
        
        # Используем временный парсер для получения количества страниц
        from .base_parser import BaseChromeParser
        temp_parser = BaseChromeParser()
        
        try:
            driver = temp_parser.driver
            
            driver.get(self.BASE)
            time.sleep(3)
            
            input_field = driver.find_element(By.ID, "search")
            input_field.send_keys(name)
            time.sleep(0.1)
            input_field.send_keys(Keys.ENTER)
            time.sleep(2)
            
            number_records = driver.find_element(By.ID, "searchResults").find_element(By.CLASS_NAME, "govuk-body").text
            pages = math.ceil(int(number_records.split()[0]) / 50)
            self.logger.info(f"[UK] Selenium found {pages} pages")
            return pages
            
        except Exception as e:
            self.logger.error(f"[UK] Selenium error: {e}")
            return 1
        finally:
            temp_parser._cleanup()

    def _norm(self, s: str) -> str:
        s = unicodedata.normalize("NFKD", (s or ""))
        return "".join(c for c in s.lower() if not unicodedata.combining(c)).strip()

    def _row_name(self, row: Dict[str, Any]) -> str:
        """Best-effort display name for OpenSearch records."""
        if not isinstance(row, dict):
            return ""
        name = (row.get("name") or "").strip()
        if name:
            return name

        names = row.get("names")
        if isinstance(names, list) and names:
            n0 = names[0] if isinstance(names[0], dict) else {}
            full = (n0.get("fullName") or "").strip()
            if full:
                return full
            parts = [n0.get("name1"), n0.get("name2"), n0.get("name3"), n0.get("name4"), n0.get("name5"), n0.get("name6")]
            parts = [str(p).strip() for p in parts if p]
            if parts:
                return " ".join(parts)
        return ""

    def _row_match_text(self, row: Dict[str, Any]) -> str:
        """Text used for matching (name + stable identifiers)."""
        if not isinstance(row, dict):
            return ""
        bits = [
            self._row_name(row),
            str(row.get("documentKey") or ""),
            str(row.get("unique_ID") or ""),
            str(row.get("uniqueId") or ""),
            str(row.get("ofsiID") or ""),
        ]
        return " ".join(b for b in bits if b).strip()

    def _match_name(self, query: str, rows: List[Dict[str, Any]]):
        if not rows:
            self.logger.debug("[UK] No rows to match against")
            return None
            
        valid_rows = [row for row in rows if isinstance(row, dict)]
        if not valid_rows:
            self.logger.warning("[UK] No valid dict rows found")
            return None
            
        names = [self._row_match_text(row) for row in valid_rows]
        norm_names = [self._norm(x) for x in names]
        q = self._norm(query)
        
        if not norm_names:
            return None
            
        best = process.extract(q, norm_names, scorer=fuzz.token_set_ratio, limit=3)
        for cand, score, idx in best:
            if score >= self.min_score:
                return valid_rows[idx], score, idx
        return None

    def _download_report(self, search_name: str, unique_id: str = None):
        if unique_id:
            url = f"{self.REPORT_FINDING_API}/{unique_id}"
            self.logger.info(f"[UK] Downloading report: {url}")
            r = self.session.get(url, timeout=60)
            if not r.ok or not r.content:
                raise RuntimeError(f"GET {url} failed: {r.status_code}")
        else:
            self.logger.info("[UK] Downloading NOT-FOUND report")
            r = self.session.post(self.REPORT_NOT_FOUND_API, json={"searchValue": search_name}, timeout=60)
            if not r.ok or not r.content:
                raise RuntimeError(f"POST {self.REPORT_NOT_FOUND_API} failed: {r.status_code}")
        
        content_type = (r.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip()
        data = r.content
        ext = ".odt" if unique_id else ".ods"
        filename = f"{search_name}_UK{ext}"
        
        return data, filename, content_type
