import os
from typing import List, Dict, Any, Optional
import pdfplumber
from pypdf import PdfReader
from app.core.exceptions import InvalidPDFException

class ExtractedPage:
    def __init__(
        self,
        page_number: int,
        text: str,
        lines: List[str],
        tables: Optional[List[List[List[Optional[str]]]]] = None,
        words: Optional[List[Dict[str, Any]]] = None
    ):
        self.page_number = page_number
        self.text = text
        self.lines = lines
        self.tables = tables or []
        self.words = words or []

class ExtractedDocument:
    def __init__(
        self,
        pages: List[ExtractedPage],
        is_digital: bool = True,
        file_path: Optional[str] = None,
        password: Optional[str] = None,
        total_file_pages: Optional[int] = None,
        start_page: int = 1,
        max_pages: Optional[int] = None
    ):
        self.pages = pages
        self.is_digital = is_digital
        self.total_pages = len(pages)
        self.total_file_pages = total_file_pages if total_file_pages is not None else len(pages)
        self.full_text = "\n".join(p.text for p in pages)
        self.first_page_text = pages[0].text if pages else ""
        self.file_path = file_path
        self.password = password
        self.start_page = start_page
        self.max_pages = max_pages
        self.page_numbers = [p.page_number for p in pages]

def extract_pdf_data(
    file_path: str,
    password: Optional[str] = None,
    extract_tables: bool = False,
    max_pages: Optional[int] = None,
    start_page: int = 1
) -> ExtractedDocument:
    """
    Extracts text, words, tables, and structured layout information from a PDF file.
    Uses pdfplumber as primary engine for precise coordinate and columnar extraction,
    with robust fallback to pypdf. Validates digital statement vs scanned.
    Supports partial page range extraction (start_page, max_pages) to avoid loading unneeded pages.
    """
    try:
        pages: List[ExtractedPage] = []
        total_chars = 0
        total_file_pages = 0

        try:
            with pdfplumber.open(file_path, password=password or None) as pdf:
                total_file_pages = len(pdf.pages)
                start_idx = max(0, start_page - 1)
                end_idx = min(total_file_pages, start_idx + max_pages) if max_pages is not None else total_file_pages

                for idx in range(start_idx, end_idx):
                    page = pdf.pages[idx]
                    text = page.extract_text(layout=False) or ""
                    total_chars += len(text.strip())
                    lines = [line.strip() for line in text.splitlines() if line.strip()]
                    
                    page_tables = []
                    if extract_tables:
                        try:
                            page_tables = page.extract_tables() or []
                        except Exception:
                            page_tables = []

                    pages.append(
                        ExtractedPage(
                            page_number=idx + 1,
                            text=text,
                            lines=lines,
                            tables=page_tables
                        )
                    )
        except Exception:
            # Fallback to pypdf
            pages = []
            total_chars = 0
            reader = PdfReader(file_path)
            if reader.is_encrypted:
                if password:
                    reader.decrypt(password)
                else:
                    reader.decrypt("")
            total_file_pages = len(reader.pages)
            start_idx = max(0, start_page - 1)
            end_idx = min(total_file_pages, start_idx + max_pages) if max_pages is not None else total_file_pages

            for idx in range(start_idx, end_idx):
                page = reader.pages[idx]
                text = page.extract_text() or ""
                total_chars += len(text.strip())
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                pages.append(ExtractedPage(page_number=idx + 1, text=text, lines=lines))

        # Heuristic for scanned PDF: very low character count across pages (only if pages were extracted)
        is_digital = (total_chars > 30 * len(pages)) if len(pages) > 0 else True

        if len(pages) > 0 and not is_digital:
            raise InvalidPDFException(
                "This document appears to be a scanned image or photo without selectable text. "
                "Kangra Hub Free Tally XML requires digitally generated PDF statements from your bank's net banking or mobile app."
            )

        return ExtractedDocument(
            pages=pages,
            is_digital=is_digital,
            file_path=file_path,
            password=password,
            total_file_pages=total_file_pages,
            start_page=start_page,
            max_pages=max_pages
        )

    except InvalidPDFException:
        raise
    except Exception as e:
        raise InvalidPDFException(f"Could not extract text from the PDF statement: {str(e)}")

def extract_pdf_header_sample(
    file_path: str,
    password: Optional[str] = None,
    max_pages: int = 3
) -> ExtractedDocument:
    """
    Quickly extracts first few pages strictly for rapid bank detection
    without reading full statements or touching unauthorized pages.
    """
    try:
        pages: List[ExtractedPage] = []
        with pdfplumber.open(file_path, password=password or None) as pdf:
            total = len(pdf.pages)
            indices_to_read = list(range(min(max_pages, total)))
            for idx in sorted(set(indices_to_read)):
                page = pdf.pages[idx]
                text = page.extract_text(layout=False) or ""
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                pages.append(ExtractedPage(page_number=idx + 1, text=text, lines=lines))

        return ExtractedDocument(
            pages=pages,
            is_digital=True,
            file_path=file_path,
            password=password,
            total_file_pages=total,
            start_page=1,
            max_pages=max_pages
        )
    except Exception:
        return extract_pdf_data(file_path, password=password, extract_tables=False, max_pages=max_pages, start_page=1)
