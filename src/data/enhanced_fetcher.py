"""
Enhanced data fetcher — BSE/NSE corporate filings + investor relations.

Fetches from:
1. screener.in (financials, ratios, shareholding)
2. NSE India (corporate announcements, annual reports, board meetings)
3. Company investor relations pages (for micro-caps)
"""
import re
import json
import time
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from loguru import logger


class EnhancedFetcher:
    """
    Multi-source data aggregator for Indian listed companies.
    Designed for micro-cap/small-cap where data may be sparse.
    """

    SCREENER_BASE = "https://www.screener.in/company"
    NSE_FILINGS_URL = "https://www.nseindia.com/api/corporate-announcements"
    NSE_ANNUAL_REPORTS_URL = "https://archives.nseindia.com/annual_reports"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/json",
        "Accept-Language": "en-IN,en;q=0.9",
    }

    # Cache directory for downloaded filings
    CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "company_cache"

    def __init__(self):
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update(self.HEADERS)

    # ---- PDF Handling ----

    def _download_and_parse_pdf(self, url: str) -> str:
        """Download PDF and extract text."""
        try:
            from src.data.pdf_parser import PDFParser
            
            # Create a localized cache for PDFs
            pdf_dir = self.CACHE_DIR / "pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            
            filename = url.split("/")[-1]
            if not filename.endswith(".pdf"):
                filename += ".pdf"
                
            pdf_path = pdf_dir / filename
            
            # Download if not cached
            if not pdf_path.exists():
                logger.info(f"Downloading PDF: {url}")
                resp = self._session.get(url, stream=True, timeout=30)
                if resp.status_code == 200:
                    with open(pdf_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    return ""
            
            # Parse
            parser = PDFParser()
            # For MVP, just get text, don't parse full tables to save tokens/time
            text, _ = parser._extract_text(pdf_path)
            
            # Limit text length? 
            # Annual reports are huge. 
            # Let's take the first 50 pages (usually contains Board Report + Auditor Report)
            # and maybe search for specific keywords later.
            # For now, return truncated text to avoid 1M token context issues if using small models
            return text[:50000] # Approx 12k tokens
            
        except Exception as e:
            logger.warning(f"PDF download/parse failed for {url}: {e}")
            return ""

    def fetch_all(self, ticker: str) -> Dict:
        """
        Fetch all available data for a company ticker.
        """
        # ... (same as before) ...
        # I need to duplicate the start of fetch_all to modify it? 
        # No, I can just use `replaced_content` carefully.
        # But `fetch_all` is big. 
        # I'll rely on the user seeing I'm updating the class.
        # Wait, I cannot use `replace_file_content` to *insert* inside a method easily without matching context.
        # I will overwrite `fetch_all` to add the PDF steps.
        
        ticker = ticker.upper().strip()
        logger.info(f"Fetching comprehensive data for {ticker}")

        profile = {
            "ticker": ticker,
            "company_name": "",
            "sector": "",
            "market_cap": "",
            "fetched_at": datetime.utcnow().isoformat(),
            "data_sources": [],
            "financials": {},
            "quarterly": {},
            "balance_sheet": {},
            "cash_flow": {},
            "ratios": {},
            "shareholding": {},
            "governance": {},
            "related_parties": {},
            "corporate_announcements": [],
            "annual_report_urls": [],
            "concall_data": [],
            "pros": [],
            "cons": [],
            # New fields
            "annual_report_text": "",
            "concall_text": "",
        }

        # 1. Screener.in
        try:
            screener_data = self._fetch_screener(ticker)
            profile.update(screener_data)
            profile["data_sources"].append("screener.in")
            logger.info(f"  ✅ screener.in: {len(screener_data.get('financials', {}))} financial rows")
        except Exception as e:
            logger.warning(f"  ❌ screener.in failed: {e}")

        # 2. NSE corporate announcements
        try:
            announcements = self._fetch_nse_announcements(ticker)
            profile["corporate_announcements"] = announcements
            profile["data_sources"].append("nse_announcements")
        except Exception as e:
            logger.warning(f"  ❌ NSE announcements failed: {e}")

        # 3. Annual report texts (Download & Parse Latest)
        try:
            ar_urls = self._extract_annual_report_urls(ticker)
            profile["annual_report_urls"] = ar_urls
            if ar_urls:
                profile["data_sources"].append("nse_annual_reports")
                # Get latest
                latest_ar = ar_urls[0]["url"]
                logger.info(f"  📄 Processing Annual Report: {latest_ar}")
                profile["annual_report_text"] = self._download_and_parse_pdf(latest_ar)
        except Exception as e:
            logger.warning(f"  ❌ Annual report processing failed: {e}")

        # 4. Concall transcripts (Download & Parse Latest)
        try:
            concalls = self._fetch_concall_links(ticker)
            profile["concall_data"] = concalls
            if concalls:
                profile["data_sources"].append("concalls")
                # Get latest transcript (prioritize transcript over PPT)
                transcript = next((c for c in concalls if c["type"] == "concall_transcript"), None)
                if transcript:
                    logger.info(f"  🎙️ Processing Transcript: {transcript['url']}")
                    profile["concall_text"] = self._download_and_parse_pdf(transcript["url"])
        except Exception as e:
            logger.warning(f"  ❌ Concall processing failed: {e}")

        # Cache the fetched data
        self._cache_data(ticker, profile)

        return profile

    # ---- Screener.in ----

    def _fetch_screener(self, ticker: str) -> Dict:
        """Fetch and parse screener.in data."""
        url = f"{self.SCREENER_BASE}/{ticker}/consolidated/"
        result = {}

        resp = self._session.get(url, timeout=15)
        if resp.status_code == 404:
            url = f"{self.SCREENER_BASE}/{ticker}/"
            resp = self._session.get(url, timeout=15)

        if resp.status_code != 200:
            raise ValueError(f"HTTP {resp.status_code} for {url}")

        soup = BeautifulSoup(resp.text, "lxml")

        # Company name
        h1 = soup.find("h1")
        if h1:
            result["company_name"] = h1.get_text(strip=True)

        # Sector - try multiple selectors
        for pattern in [r"/sector/", r"/market/"]:
            sector_elem = soup.find("a", {"href": re.compile(pattern)})
            if sector_elem:
                result["sector"] = sector_elem.get_text(strip=True)
                break

        # Key ratios
        result["ratios"] = self._extract_ratios(soup)

        # Market cap from ratios
        if "Market Cap" in result.get("ratios", {}):
            result["market_cap"] = result["ratios"]["Market Cap"]

        # Pros and cons
        result["pros"] = self._extract_list(soup, "pros")
        result["cons"] = self._extract_list(soup, "cons")

        # Financial tables
        for section, key in [
            ("profit-loss", "financials"),
            ("quarters", "quarterly"),
            ("balance-sheet", "balance_sheet"),
            ("cash-flow", "cash_flow"),
            ("shareholding", "shareholding"),
        ]:
            result[key] = self._extract_table(soup, section)

        return result

    def _extract_ratios(self, soup: BeautifulSoup) -> Dict:
        """Extract ratios from the page header."""
        ratios = {}

        # Try #top-ratios first
        ratio_list = soup.find("ul", {"id": "top-ratios"})
        if not ratio_list:
            ratio_list = soup.find("div", {"class": "company-ratios"})

        if ratio_list:
            for li in ratio_list.find_all("li"):
                name_el = li.find("span", {"class": "name"})
                num_el = li.find("span", {"class": "number"}) or li.find("b")
                if name_el and num_el:
                    ratios[name_el.get_text(strip=True)] = num_el.get_text(strip=True)

        # Also try the top-level list items (sometimes no class)
        if not ratios:
            top_section = soup.find("div", {"id": "top"})
            if top_section:
                for li in top_section.find_all("li"):
                    text = li.get_text(strip=True)
                    parts = text.split("₹")
                    if len(parts) == 2:
                        ratios[parts[0].strip()] = f"₹{parts[1].strip()}"

        return ratios

    def _extract_list(self, soup: BeautifulSoup, css_class: str) -> List[str]:
        """Extract pros or cons list."""
        items = []
        div = soup.find("div", {"class": css_class})
        if div:
            for li in div.find_all("li"):
                text = li.get_text(strip=True)
                if text:
                    items.append(text)
        return items

    def _extract_table(self, soup: BeautifulSoup, section_id: str) -> Dict:
        """Extract table data from a screener section."""
        section = soup.find("section", {"id": section_id})
        if not section:
            return {}

        table = section.find("table")
        if not table:
            return {}

        result = {}
        try:
            # Headers (years or quarters)
            headers = []
            thead = table.find("thead")
            if thead:
                header_row = thead.find("tr")
                if header_row:
                    headers = [
                        th.get_text(strip=True)
                        for th in header_row.find_all("th")
                    ]

            # Rows
            tbody = table.find("tbody")
            if tbody:
                for row in tbody.find_all("tr"):
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        values = [c.get_text(strip=True) for c in cells[1:]]
                        if len(headers) > 1:
                            result[label] = dict(zip(headers[1:], values))
                        else:
                            result[label] = values
        except Exception as e:
            logger.debug(f"Table parse error for {section_id}: {e}")

        return result

    # ---- NSE Announcements ----

    def _fetch_nse_announcements(self, ticker: str) -> List[Dict]:
        """
        Fetch corporate announcements from NSE India.
        Uses screener.in as a proxy since NSE API needs cookies.
        """
        announcements = []

        # Scrape announcements from the screener.in page (they embed NSE links)
        url = f"{self.SCREENER_BASE}/{ticker}/consolidated/"
        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code == 404:
                url = f"{self.SCREENER_BASE}/{ticker}/"
                resp = self._session.get(url, timeout=15)

            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            # Find the documents section
            docs = soup.find("section", {"id": "documents"}) or soup
            links = docs.find_all("a", href=re.compile(r"nsearchives|nseindia"))

            for link in links:
                href = link.get("href", "")
                text = link.get_text(strip=True)

                if not text or len(text) < 5:
                    continue

                # Parse date if available
                parent = link.find_parent("li") or link.find_parent("div")
                date_text = ""
                if parent:
                    date_text = parent.get_text(strip=True)

                ann = {
                    "title": text[:200],
                    "url": href,
                    "type": self._classify_filing(text, href),
                    "date": self._extract_date(date_text),
                }
                announcements.append(ann)

        except Exception as e:
            logger.warning(f"NSE announcements parse error: {e}")

        return announcements

    def _classify_filing(self, title: str, url: str) -> str:
        """Classify a filing by its title/URL."""
        title_lower = title.lower()
        url_lower = url.lower()

        if any(k in title_lower for k in ["annual report", "annual_report"]):
            return "annual_report"
        if any(k in title_lower for k in ["board meeting", "outcome"]):
            return "board_meeting"
        if any(k in title_lower for k in ["buyback"]):
            return "buyback"
        if any(k in title_lower for k in ["press release"]):
            return "press_release"
        if any(k in title_lower for k in ["financial result", "quarterly"]):
            return "financial_results"
        if any(k in title_lower for k in ["concall", "conference call", "investor call"]):
            return "concall"
        if any(k in url_lower for k in ["annual_report"]):
            return "annual_report"
        return "other"

    def _extract_date(self, text: str) -> str:
        """Try to extract a date from surrounding text."""
        # Match patterns like "13 November 2025", "9 January 2026"
        match = re.search(
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|"
            r"August|September|October|November|December)\s+\d{4})",
            text,
        )
        if match:
            return match.group(1)
        return ""

    # ---- Annual Reports ----

    def _extract_annual_report_urls(self, ticker: str) -> List[Dict]:
        """Extract annual report PDF URLs from screener page."""
        reports = []
        url = f"{self.SCREENER_BASE}/{ticker}/consolidated/"

        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code == 404:
                url = f"{self.SCREENER_BASE}/{ticker}/"
                resp = self._session.get(url, timeout=15)

            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            # Find annual report links specifically
            for link in soup.find_all("a", href=re.compile(r"annual_report.*\.pdf")):
                href = link.get("href", "")
                text = link.get_text(strip=True)

                # Extract financial year
                fy_match = re.search(r"(\d{4})", text)
                fy = fy_match.group(1) if fy_match else ""

                reports.append({
                    "url": href,
                    "financial_year": f"FY{fy}" if fy else text,
                    "type": "annual_report",
                    "source": "nse_archives",
                })

        except Exception as e:
            logger.warning(f"Annual report URL extraction failed: {e}")

        return reports

    # ---- Concalls ----

    def _fetch_concall_links(self, ticker: str) -> List[Dict]:
        """Fetch concall/investor presentation links."""
        concalls = []
        url = f"{self.SCREENER_BASE}/{ticker}/consolidated/"

        try:
            resp = self._session.get(url, timeout=15)
            if resp.status_code == 404:
                url = f"{self.SCREENER_BASE}/{ticker}/"
                resp = self._session.get(url, timeout=15)

            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            for link in soup.find_all(
                "a",
                href=re.compile(r"concall|conference|investor|ppt|presentation", re.I),
            ):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if len(text) >= 3:
                    concalls.append({
                        "title": text[:200],
                        "url": href,
                        "type": "concall_transcript" if "transcript" in href.lower() else "investor_presentation",
                    })

        except Exception as e:
            logger.warning(f"Concall link extraction failed: {e}")

        return concalls

    # ---- Caching ----

    def _cache_data(self, ticker: str, data: dict):
        """Cache fetched data to a local JSON file."""
        cache_file = self.CACHE_DIR / f"{ticker}.json"
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"  💾 Cached to {cache_file}")

    def load_cached(self, ticker: str) -> Optional[Dict]:
        """Load cached data for a ticker."""
        cache_file = self.CACHE_DIR / f"{ticker.upper()}.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        return None

    # ---- Batch fetch ----

    def fetch_batch(
        self, tickers: List[str], delay: float = 2.0
    ) -> Dict[str, Dict]:
        """Fetch data for multiple tickers with rate limiting."""
        results = {}
        for i, ticker in enumerate(tickers):
            logger.info(f"\n📊 [{i+1}/{len(tickers)}] Fetching {ticker}...")
            try:
                results[ticker] = self.fetch_all(ticker)
            except Exception as e:
                logger.error(f"  ❌ Failed: {e}")
                results[ticker] = {"ticker": ticker, "error": str(e)}

            if i < len(tickers) - 1:
                time.sleep(delay)  # Rate limiting

        return results
