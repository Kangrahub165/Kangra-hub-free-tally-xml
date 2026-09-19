from abc import ABC, abstractmethod
from typing import Optional
from app.pdf.extractor import ExtractedDocument
from app.transactions.model import CanonicalStatement

class BaseStatementParser(ABC):
    """Abstract base class for all bank statement parsers."""

    def __init__(self, bank_name: str, format_name: str, parser_key: str, version: str = "1.0"):
        self.bank_name = bank_name
        self.format_name = format_name
        self.parser_key = parser_key
        self.version = version

    @abstractmethod
    def can_parse(self, doc: ExtractedDocument) -> bool:
        """Determines if this parser is compatible with the document layout."""
        pass

    @abstractmethod
    def parse(self, doc: ExtractedDocument) -> CanonicalStatement:
        """Extracts and normalizes transactions into the CanonicalStatement model."""
        pass
