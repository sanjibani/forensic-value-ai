"""
Data fetcher — Aggregates company data from public sources.

Scrapes screener.in for financials, shareholding, ratios.
Supports BSE India for corporate filings (to be expanded).
"""
import re
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger


class DataFetcher:
    """
    Coordinates data fetching from multiple public sources.
    Returns a unified company profile dict.
    """

    SCREENER_BASE = "https://www.screener.in/company"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    def fetch_company_data(self, ticker: str) -> Dict:
        """
        Fetch all available data for a company.

        Args:
            ticker: NSE ticker symbol (e.g., "INFY", "RELIANCE")

        Returns:
            Unified company profile dict
        """
        profile = {
            "ticker": ticker.upper(),
            "company_name": "",
            "sector": "",
            "financials": {},
            "ratios": {},
            "shareholding": {},
            "quarterly": {},
            "governance": {},
            "related_parties": {},
        }

        # Try screener.in first
        try:
            screener_data = self._fetch_screener(ticker)
            profile.update(screener_data)
        except Exception as e:
            logger.warning(f"Screener.in fetch failed for {ticker}: {e}")

        return profile

    def _fetch_screener(self, ticker: str) -> Dict:
        """
        Scrape screener.in for financial data.

        Extracts:
        - Company name and sector
        - Key ratios (PE, ROCE, ROE, etc.)
        - Annual financial data (5 years)
        - Quarterly results
        - Shareholding pattern
        """
        url = f"{self.SCREENER_BASE}/{ticker}/consolidated/"
        result = {}

        try:
            resp = requests.get(url, headers=self.HEADERS, timeout=15)
            if resp.status_code == 404:
                # Try standalone (non-consolidated)
                url = f"{self.SCREENER_BASE}/{ticker}/"
                resp = requests.get(url, headers=self.HEADERS, timeout=15)

            if resp.status_code != 200:
                raise ValueError(f"HTTP {resp.status_code} for {url}")

            soup = BeautifulSoup(resp.text, "lxml")

            # Company name
            h1 = soup.find("h1")
            if h1:
                result["company_name"] = h1.get_text(strip=True)

            # Sector
            sector_elem = soup.find("a", {"href": re.compile(r"/sector/")})
            if sector_elem:
                result["sector"] = sector_elem.get_text(strip=True)

            # Key ratios from the top section
            result["ratios"] = self._extract_ratios(soup)

            # Profit & Loss (annual)
            result["financials"] = self._extract_table(soup, "profit-loss")

            # Quarterly results
            result["quarterly"] = self._extract_table(soup, "quarters")

            # Balance Sheet
            result["balance_sheet"] = self._extract_table(soup, "balance-sheet")

            # Cash Flow
            result["cash_flow"] = self._extract_table(soup, "cash-flow")

            # Shareholding
            result["shareholding"] = self._extract_table(soup, "shareholding")

        except requests.RequestException as e:
            logger.warning(f"Network error fetching screener data: {e}")
        except Exception as e:
            logger.warning(f"Error parsing screener data for {ticker}: {e}")

        return result

    def _extract_ratios(self, soup: BeautifulSoup) -> Dict:
        """Extract key ratios from the header section."""
        ratios = {}
        ratio_list = soup.find("ul", {"id": "top-ratios"})
        if not ratio_list:
            # Try alternative locations
            ratio_list = soup.find("div", {"class": "company-ratios"})

        if ratio_list:
            items = ratio_list.find_all("li")
            for item in items:
                name_elem = item.find("span", {"class": "name"})
                value_elem = item.find("span", {"class": "number"})
                if name_elem and value_elem:
                    name = name_elem.get_text(strip=True)
                    value = value_elem.get_text(strip=True)
                    ratios[name] = value

        return ratios

    def _extract_table(
        self, soup: BeautifulSoup, section_id: str
    ) -> Dict:
        """Extract a data table from screener.in by section ID."""
        section = soup.find("section", {"id": section_id})
        if not section:
            return {}

        table = section.find("table")
        if not table:
            return {}

        result = {}
        try:
            # Extract headers (years/quarters)
            thead = table.find("thead")
            if thead:
                header_row = thead.find("tr")
                if header_row:
                    headers = [
                        th.get_text(strip=True)
                        for th in header_row.find_all("th")
                    ]
                else:
                    headers = []
            else:
                headers = []

            # Extract rows
            tbody = table.find("tbody")
            if tbody:
                for row in tbody.find_all("tr"):
                    cells = row.find_all(["td", "th"])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True)
                        values = [
                            c.get_text(strip=True) for c in cells[1:]
                        ]
                        result[label] = dict(
                            zip(headers[1:], values)
                        ) if len(headers) > 1 else values
        except Exception as e:
            logger.debug(f"Table extraction error for {section_id}: {e}")

        return result

    @staticmethod
    def build_sample_data(ticker: str) -> Dict:
        """
        Generate sample company data for testing when scraping fails.

        This provides realistic-looking data structure for development.
        """
        return {
            "ticker": ticker.upper(),
            "company_name": f"{ticker.upper()} Ltd",
            "sector": "Information Technology",
            "financials": {
                "Revenue": {
                    "Mar 2024": "164,000", "Mar 2023": "146,767",
                    "Mar 2022": "121,641", "Mar 2021": "100,472",
                    "Mar 2020": "90,791",
                },
                "Net Profit": {
                    "Mar 2024": "26,233", "Mar 2023": "24,108",
                    "Mar 2022": "22,110", "Mar 2021": "19,351",
                    "Mar 2020": "16,594",
                },
                "Operating Cash Flow": {
                    "Mar 2024": "27,800", "Mar 2023": "23,500",
                    "Mar 2022": "24,100", "Mar 2021": "22,000",
                    "Mar 2020": "18,900",
                },
                "Trade Receivables": {
                    "Mar 2024": "28,500", "Mar 2023": "24,100",
                    "Mar 2022": "21,300", "Mar 2021": "18,500",
                    "Mar 2020": "17,200",
                },
                "Inventory": {
                    "Mar 2024": "0", "Mar 2023": "0",
                    "Mar 2022": "0", "Mar 2021": "0",
                    "Mar 2020": "0",
                },
            },
            "ratios": {
                "Market Cap": "₹ 6,50,000 Cr",
                "Stock P/E": "25.8",
                "ROCE": "38.5 %",
                "ROE": "32.1 %",
                "Debt to Equity": "0.08",
                "Promoter Holding": "14.95 %",
            },
            "shareholding": {
                "Promoter": {
                    "Dec 2024": "14.95%", "Sep 2024": "14.95%",
                    "Jun 2024": "15.10%", "Mar 2024": "15.10%",
                },
                "FII": {
                    "Dec 2024": "36.28%", "Sep 2024": "35.82%",
                    "Jun 2024": "34.91%", "Mar 2024": "35.22%",
                },
                "DII": {
                    "Dec 2024": "35.20%", "Sep 2024": "35.10%",
                    "Jun 2024": "35.50%", "Mar 2024": "35.80%",
                },
                "Public": {
                    "Dec 2024": "13.57%", "Sep 2024": "14.13%",
                    "Jun 2024": "14.49%", "Mar 2024": "13.88%",
                },
            },
            "governance": {
                "board_size": 16,
                "independent_directors": 9,
                "women_directors": 3,
                "audit_committee_independent": True,
                "auditor": "Deloitte Haskins & Sells LLP",
                "auditor_tenure_years": 5,
            },
            "related_parties": {
                "Infrastructure subsidiary": "₹ 2,100 Cr (facilities)",
                "Consulting subsidiary": "₹ 850 Cr (IT services)",
                "Foundation": "₹ 340 Cr (CSR contributions)",
            },
        }
