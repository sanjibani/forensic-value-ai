"""
PDF parser for extracting structured data from annual reports.
"""
from typing import Dict, List, Optional
from pathlib import Path

from loguru import logger


class PDFParser:
    """
    Extracts text, tables, and structured data from annual report PDFs.

    Uses pdfplumber for table extraction and pypdf for text extraction.
    Falls back to LLM-assisted parsing for complex layouts.
    """

    def extract(self, pdf_path: str) -> Dict:
        """
        Extract all data from a PDF annual report.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Dict with 'text', 'tables', and 'metadata' keys
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        result = {
            "filename": path.name,
            "text": "",
            "tables": [],
            "metadata": {},
            "pages": 0,
        }

        # Extract text with pypdf
        try:
            text, pages = self._extract_text(path)
            result["text"] = text
            result["pages"] = pages
        except Exception as e:
            logger.warning(f"Text extraction failed: {e}")

        # Extract tables with pdfplumber
        try:
            result["tables"] = self._extract_tables(path)
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")

        return result

    def _extract_text(self, path: Path) -> tuple[str, int]:
        """Extract text from all pages using pypdf."""
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = len(reader.pages)
        texts = []

        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                texts.append(f"--- Page {i + 1} ---\n{text}")

        return "\n\n".join(texts), pages

    def _extract_tables(self, path: Path) -> List[Dict]:
        """Extract tables using pdfplumber."""
        import pdfplumber

        tables = []
        with pdfplumber.open(str(path)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_tables = page.extract_tables()
                for j, table in enumerate(page_tables):
                    if table and len(table) > 1:
                        # First row as headers
                        headers = [str(h).strip() if h else f"col_{k}"
                                   for k, h in enumerate(table[0])]
                        rows = []
                        for row in table[1:]:
                            row_dict = {}
                            for k, cell in enumerate(row):
                                key = headers[k] if k < len(headers) else f"col_{k}"
                                row_dict[key] = str(cell).strip() if cell else ""
                            rows.append(row_dict)

                        tables.append({
                            "page": i + 1,
                            "table_index": j,
                            "headers": headers,
                            "rows": rows,
                        })

        return tables

    def extract_section(
        self, pdf_path: str, section_name: str
    ) -> Optional[str]:
        """
        Extract a specific named section from the PDF.

        Args:
            pdf_path: Path to PDF
            section_name: Name like "Related Party Transactions",
                         "Auditor Report", etc.

        Returns:
            Section text or None
        """
        full_text, _ = self._extract_text(Path(pdf_path))
        section_lower = section_name.lower()

        # Try to find section boundaries
        lines = full_text.split("\n")
        start_idx = None
        end_idx = None

        for i, line in enumerate(lines):
            if section_lower in line.lower():
                start_idx = i
            elif start_idx and i > start_idx + 5:
                # Check if we hit another major section header
                stripped = line.strip()
                if (
                    stripped
                    and stripped[0].isupper()
                    and len(stripped) < 100
                    and stripped.endswith((":", "."))
                ):
                    end_idx = i
                    break

        if start_idx is not None:
            end_idx = end_idx or min(start_idx + 200, len(lines))
            return "\n".join(lines[start_idx:end_idx])

        return None
