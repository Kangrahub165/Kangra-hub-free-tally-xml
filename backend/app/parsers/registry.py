from typing import Dict, List, Optional
from app.parsers.base import BaseStatementParser
from app.parsers.generic_standard import GenericStandardParser
from app.parsers.pnb import PNBParser
from app.parsers.sbi import SBIParser
from app.parsers.axis import AxisBankParser
from app.parsers.union_bank import UnionBankParser
from app.parsers.uco import UCOBankParser
from app.parsers.hdfc import HDFCBankParser
from app.parsers.icici import ICICIBankParser
from app.parsers.kangra_coop import KangraCoopParser
from app.detector.signatures import BANK_SIGNATURES
from app.pdf.extractor import ExtractedDocument

class ParserRegistry:
    """Central registry of all bank statement parsers."""

    def __init__(self):
        self._parsers: Dict[str, BaseStatementParser] = {}
        self._register_default_parsers()

    def _register_default_parsers(self):
        # Register specialized parsers (highest priority)
        pnb = PNBParser()
        self.register(pnb)
        
        sbi = SBIParser()
        self.register(sbi)

        axis = AxisBankParser()
        self.register(axis)

        union = UnionBankParser()
        self.register(union)

        uco = UCOBankParser()
        self.register(uco)

        hdfc = HDFCBankParser()
        self.register(hdfc)

        icici = ICICIBankParser()
        self.register(icici)

        kccb = KangraCoopParser()
        self.register(kccb)

        # Register standard parsers for all remaining target banks
        for sig in BANK_SIGNATURES:
            key = sig["parser_key"]
            if key not in self._parsers:
                generic_bank_parser = GenericStandardParser(
                    bank_name=sig["bank_name"],
                    format_name="Standard",
                    parser_key=key,
                    version="1.0"
                )
                self.register(generic_bank_parser)

        # Register fallback standard parser
        generic_fallback = GenericStandardParser(
            bank_name="Generic Bank",
            format_name="Standard",
            parser_key="generic_standard",
            version="1.0"
        )
        self.register(generic_fallback)

    def register(self, parser: BaseStatementParser):
        self._parsers[parser.parser_key] = parser

    def get_parser(self, parser_key: str) -> Optional[BaseStatementParser]:
        return self._parsers.get(parser_key)

    def get_parser_for_bank(self, bank_name: str) -> Optional[BaseStatementParser]:
        clean_target = bank_name.lower().strip()
        for p in self._parsers.values():
            if p.bank_name.lower().strip() == clean_target:
                return p
        for p in self._parsers.values():
            if clean_target in p.bank_name.lower() or p.bank_name.lower() in clean_target:
                return p
        return None

    def list_all_parsers(self) -> List[Dict[str, str]]:
        return [
            {
                "parser_key": p.parser_key,
                "bank_name": p.bank_name,
                "format_name": p.format_name,
                "version": p.version,
                "is_active": True
            }
            for p in self._parsers.values()
        ]

parser_registry = ParserRegistry()
