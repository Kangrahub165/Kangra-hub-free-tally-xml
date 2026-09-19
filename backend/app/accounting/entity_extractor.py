import re
from typing import Optional, Tuple, Dict, Any

class NarrationEntityExtractor:
    """
    Intelligently extracts beneficiary/party entities, cheque/instrument numbers,
    and reference IDs from Indian bank statement narrations.
    Conforms strictly to 32-point accounting classification specifications.
    """

    # Comprehensive Bank Charges Pattern (Section 4 & 5 of specification)
    BANK_CHARGES_PATTERN = re.compile(
        r'\b(?:'
        # Core charge combinations
        r'BANK\s+CHARGES?|BANK\s+CHGS?|BANK\s+CHRG|SERVICE\s+CHARGES?|SERVICE\s+CHGS?|SERVICE\s+CHRG|'
        # Account Maintenance & Keeping
        r'A/?C\s+MAINT(?:ENANCE)?(?:\s+CHARGES?|\s+CHGS?|\s+CHRG)?|'
        r'ACC(?:OUNT)?\s+MAINT(?:ENANCE)?(?:\s+CHARGES?|\s+CHGS?|\s+CHRG)?|'
        r'MAINTENANCE\s+CHARGES?|MAINT\s+CHGS?|AMC|ANNUAL\s+MAINTENANCE\s+CHARGES?|'
        r'A/?C\s+KEEPING(?:\s+CHARGES?|\s+CHGS?|\s+CHRG)?|'
        r'ACC(?:OUNT)?\s+KEEPING(?:\s+CHARGES?|\s+CHGS?|\s+CHRG)?|'
        # SMS & Alerts
        r'SMS\s+ALERT(?:\s+CHARGES?|\s+CHGS?|\s+CHRG)?|SMS\s+CHARGES?|SMS\s+CHGS?|SMS\s+CHRG|'
        # Electronic Transfer Charges
        r'RTGS\s+CHARGES?|RTGS\s+CHGS?|RTGS\s+CHRG|'
        r'NEFT\s+CHARGES?|NEFT\s+CHGS?|NEFT\s+CHRG|'
        r'IMPS\s+CHARGES?|IMPS\s+CHGS?|IMPS\s+CHRG|'
        r'UPI\s+CHARGES?|UPI\s+CHGS?|UPI\s+CHRG|'
        r'FUND\s+TRANSFER\s+CHARGES?|FUND\s+TRF\s+CHG|'
        # Cash handling & Cards
        r'CASH\s+HANDLING\s+CHARGES?|CASH\s+HANDLING\s+CHG|'
        r'CHEQUE\s+CHARGES?|CHEQUE\s+RETURN\s+CHARGES?|CHEQUE\s+BOUNCE\s+CHARGES?|'
        r'CHQ\s+RETURN\s+CHG|CHQ\s+BOUNCE\s+CHG|RETURN\s+CHARGES?|PENAL\s+CHARGES?|'
        r'PROCESSING\s+CHARGES?|TRANSACTION\s+CHARGES?|'
        r'DEBIT\s+CARD\s+CHARGES?|CARD\s+CHARGES?|POS\s+CHARGES?|E-?COM\s+CHARGES?|'
        r'ANNUAL\s+FEE|CONSOLIDATED\s+CHG|'
        # GST on Bank Charges
        r'(?:GST|CGST|SGST|IGST)\s+ON\s+BANK\s+CHARGES?|'
        # Specific bank descriptions
        r'Charges\s+for\s+NEFT\s+Customer\s+Payment|'
        r'Charges\s+for\s+RTGS\s+Customer\s+Payment|'
        # Standalone charge indicators
        r'CHARGES?|CHGS?|CHRG'
        r')\b',
        re.IGNORECASE
    )

    # Cash Deposit Patterns (Section 2 & 3)
    CASH_DEPOSIT_PATTERN = re.compile(
        r'\b(?:'
        r'CASH\s+DEP(?:OSIT)?(?:ED)?|CASH\s+DEPOSIT\s+BY\s+SELF|BY\s+CASH|'
        r'CDM\s+CASH|CDM\s+DEP|CASH\s+RECD|DEPOSIT\s+BY\s+CASH|CASH\s+DEPOSIT\s+AT'
        r')\b',
        re.IGNORECASE
    )

    # Cash Withdrawal Patterns (Section 2 & 3)
    CASH_WITHDRAWAL_PATTERN = re.compile(
        r'\b(?:'
        r'ATM\s+CASH\s+WITHDRAWAL|CASH\s+WITHDRAWAL\s+THROUGH\s+ATM|'
        r'CASH\s+WITHDRAWAL|WITHDRAWAL\s+BY\s+CASH|CASH\s+WDL|'
        r'CASH\s+WITHDRAWAL\s+BY\s+SELF|SELF\s+CASH\s+WITHDRAWAL|'
        r'CASH\s+WITHDRAWAL\s+CHEQUE|ATM\s+CASH|ATM\s+WDL|'
        r'SELF\s+CASH|SELF\s+WDL|TO\s+CASH'
        r')\b',
        re.IGNORECASE
    )

    @staticmethod
    def clean_narration_noise(narration: str) -> str:
        """Strips watermark, latency, and layout noise from narration."""
        if not narration:
            return ""
        text = narration
        # Remove PNB latency markers: "-1 LAT", "-1 LATENCY", "LATENCY-1 LAT"
        text = re.sub(r'\s*-\s*\d+\s*LAT(?:ENCY)?\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s*-\s*LAT(?:ENCY)?\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bLATENCY\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bLAT\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bCTO\d+\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bDisclaimer:\s*This\s+is\s+an\s+Electronically\s+Generated.*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s{2,}', ' ', text).strip()
        return text

    @classmethod
    def extract_cheque_or_instrument_number(cls, narration: str, reference: Optional[str] = None) -> Optional[str]:
        """
        Extracts cheque or instrument number preserving leading zeros (e.g. "000123" or "689744").
        """
        # 1. Check dedicated reference string first
        if reference and reference.strip():
            ref_clean = reference.strip()
            if re.fullmatch(r'\d{5,8}', ref_clean):
                return ref_clean
            m_ref = re.search(r'\b(?:CHQ|CHEQUE|INST|INSTRUMENT)?\s*[:\-\./]?\s*(\d{5,8})\b', ref_clean, re.IGNORECASE)
            if m_ref:
                return m_ref.group(1)

        # 2. Check narration
        text = narration.strip()
        
        # Explicit IZE/CHQ/CHEQUE pattern (Common in PNB: "IZE 689744")
        m_ize = re.search(r'\b(?:IZE|CHQ|CHEQUE|INST|INSTRUMENT|CLR)\b\s*[:\-\./#]?\s*(\d{5,8})\b', text, re.IGNORECASE)
        if m_ize:
            return m_ize.group(1)

        # Slash-enclosed cheque e.g. CHEQUE/123456/
        m_slash = re.search(r'/(?:CHQ/)?(\d{6})/', text, re.IGNORECASE)
        if m_slash:
            return m_slash.group(1)

        # Standalone 6-digit cheque with keyword context
        m_any = re.search(r'(?:^|\s|/|-|:)(\d{6})(?:\s|/|-|$)', text)
        if m_any:
            candidate = m_any.group(1)
            # Exclude if it looks like a date (202404 or 010424) or PIN code unless surrounded by banking terms
            if not candidate.startswith(("19", "20", "202", "201")):
                start = max(0, m_any.start() - 15)
                end = min(len(text), m_any.end() + 15)
                window = text[start:end].upper()
                if any(k in window for k in ("CHQ", "CHEQUE", "CLEARING", "TRANSFER", "INST", "IZE", "TRADI")):
                    return candidate

        return None

    @staticmethod
    def extract_upi_reference(narration: str) -> Optional[str]:
        """Extracts 12-digit UPI RRN (Retrieval Reference Number)."""
        m = re.search(r'\b(?:UPI/)?(\d{12})\b', narration)
        if m:
            return m.group(1)
        return None

    @staticmethod
    def extract_utr_reference(narration: str) -> Optional[str]:
        """Extracts NEFT/RTGS UTR number (e.g. SBIN424102938472 or PUNBR52024...)."""
        m = re.search(r'\b([A-Z]{4}[A-Z0-9]{12,18})\b', narration.upper())
        if m:
            candidate = m.group(1)
            if not candidate.startswith(("HTTP", "WWW.")):
                return candidate
        return None

    @classmethod
    def identify_cash_transaction(cls, narration: str, is_debit: bool) -> Tuple[bool, Optional[str]]:
        """
        Identifies whether a transaction is a genuine physical cash deposit or cash withdrawal.
        Returns: (is_cash, cash_type) where cash_type is 'CASH_DEPOSIT' or 'CASH_WITHDRAWAL'.
        """
        cleaned = cls.clean_narration_noise(narration)
        text = cleaned.upper()

        # Cash Deposit patterns
        if cls.CASH_DEPOSIT_PATTERN.search(cleaned):
            return True, "CASH_DEPOSIT"
        if not is_debit and "BY CASH" in text:
            return True, "CASH_DEPOSIT"

        # Cash Withdrawal patterns
        if cls.CASH_WITHDRAWAL_PATTERN.search(cleaned):
            return True, "CASH_WITHDRAWAL"
        if is_debit and ("ATM" in text or "CASH WDL" in text or "SELF WDL" in text):
            return True, "CASH_WITHDRAWAL"

        # Explicit standalone word "CASH"
        if re.search(r'\b(?:CASH)\b', text):
            if is_debit:
                return True, "CASH_WITHDRAWAL"
            else:
                return True, "CASH_DEPOSIT"

        return False, None

    @classmethod
    def extract_party_from_narration(cls, narration: str, is_debit: bool = True) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts the counterparty / beneficiary entity and accounting category from narration.
        Returns: (party_name, category)
        e.g. ("BABA BALAK NATH", "RTGS"), ("Bank Charges", "BANK_CHARGES"), ("Cash", "CASH_DEPOSIT")
        """
        cleaned = cls.clean_narration_noise(" ".join(narration.strip().split()))
        upper_text = cleaned.upper()

        # 1. Physical Cash Movement (Section 2 & 3)
        is_cash, cash_type = cls.identify_cash_transaction(cleaned, is_debit)
        if is_cash:
            return "Cash", cash_type

        # 2. Bank Charges & Statutory Categories (Section 4 & 5)
        # Outgoing / Debit with bank charges terminology
        if is_debit and cls.BANK_CHARGES_PATTERN.search(cleaned):
            return "Bank Charges", "BANK_CHARGES"

        # Tax / GST on Bank Charges
        if any(k in upper_text for k in ("GST ON BANK CHARGES", "CGST ON BANK CHARGES", "SGST ON BANK CHARGES", "IGST ON BANK CHARGES")):
            return "Bank Charges", "BANK_CHARGES"
        if any(k in upper_text for k in ("GST:", "IGST:", "CGST:", "SGST:", "GST RECD")):
            return "GST Input Tax Credit", "TAX"

        # Interest Expense / Income
        if any(k in upper_text for k in ("INT.PD", "INTEREST PAID", "INTEREST DEBIT")):
            return "Bank Interest Expense", "INTEREST"
        if any(k in upper_text for k in ("INTEREST RECEIVED", "INTEREST CREDIT", "INT RECD", "INT.COLL")):
            return "Bank Interest Income", "INTEREST"

        # Pension / Statutory
        if "APY CONTRI" in upper_text:
            return "APY Contribution", "PENSION"

        # 3. RTGS / NEFT Outgoing or Incoming
        # Pattern: "RTGS OUT : PUNBR...: BABA BALAK NATH" or "NEFT OUT: PUNBN...: PRINCIPAL DAV..."
        m_out = re.search(r'\b(?:RTGS|NEFT)\s*(?:OUT|IN)?\s*:\s*[A-Z0-9]+\s*:\s*([^:\-/]+)', cleaned, re.IGNORECASE)
        if m_out:
            candidate = m_out.group(1).strip()
            # Clean trailing IFSC or tokens
            candidate = re.sub(r'\b[A-Z]{4}0[A-Z0-9]{6}\b', '', candidate).strip()
            if len(candidate) > 2 and not candidate.isdigit():
                return candidate, "RTGS" if "RTGS" in upper_text else "NEFT"

        # 4. Paid To / Beneficiary
        m_paid = re.search(r'Paid To\s*:\s*(?:TO\s+)?([^:\-/]+)', cleaned, re.IGNORECASE)
        if m_paid:
            candidate = m_paid.group(1).strip()
            # Clean trailing IZE or Cheque markers
            candidate = re.sub(r'\bIZE\s+\d+.*', '', candidate).strip()
            if len(candidate) > 2:
                return candidate, "TRANSFER"

        # 5. Cheque / Clearing
        m_ize = re.search(r'\bIZE\s+\d{5,8}\s+([^:\-/]+)', cleaned, re.IGNORECASE)
        if m_ize:
            candidate = m_ize.group(1).strip()
            candidate = re.sub(r'\b[A-Z]{4}0[A-Z0-9]{6}\b', '', candidate).strip()
            if len(candidate) > 2:
                return candidate, "CHEQUE"
        if "CLEARING" in upper_text:
            return "Clearing", "CHEQUE"

        # 6. UPI Parsing
        if upper_text.startswith("UPI/") or "/UPI/" in upper_text or " UPI " in upper_text or upper_text.startswith("UPI-") or "UPI" in upper_text:
            # Trailing after @vpa/PARTY or @bank/PARTY
            m_vpa = re.search(r'@[a-zA-Z0-9_\.\-]+/([^/]+)$', cleaned)
            if m_vpa:
                candidate = m_vpa.group(1).strip()
                # Clean trailing dates
                candidate = re.sub(r'\b\d{2}-\d{2}-\d{4}\b', '', candidate).strip()
                candidate = re.sub(r'\b\d{2}/\d{2}/\d{4}\b', '', candidate).strip()
                if len(candidate) > 2 and not candidate.isdigit():
                    return candidate, "UPI"

            tokens = [t.strip() for t in cleaned.split('/') if t.strip()]
            if len(tokens) >= 2:
                ignored_tokens = {"UPI", "P2M", "P2V", "P2A", "P2P", "NA", "CR", "DR", "PAY", "BIL", "LAT", "LATENCY"}
                for tok in reversed(tokens):
                    u_tok = tok.upper()
                    if u_tok not in ignored_tokens and not tok.isdigit() and len(tok) > 2:
                        if "@" in tok:
                            tok = tok.split("@")[0]
                        tok = re.sub(r'\b\d{2}-\d{2}-\d{4}\b', '', tok).strip()
                        if len(tok) > 2 and not tok.isdigit():
                            return tok.strip(), "UPI"

        # 7. Standard NEFT / RTGS with delimiters
        if "NEFT" in upper_text or "RTGS" in upper_text:
            tokens = [t.strip() for t in re.split(r'[/:\-]', cleaned) if t.strip()]
            ignored_tokens = {"NEFT", "RTGS", "TRANSFER", "TO", "BY", "CR", "DR", "CMS", "OUT", "IN"}
            for tok in reversed(tokens):
                u_tok = tok.upper()
                if u_tok not in ignored_tokens and len(tok) > 2:
                    if re.match(r'^[A-Z0-9]{5,18}$', u_tok) and any(c.isdigit() for c in u_tok):
                        continue
                    if not re.match(r'^[A-Z]{4}0\d{6,14}$', u_tok):
                        return tok.strip(), "NEFT"

        # 8. IMPS Parsing
        if "IMPS" in upper_text:
            tokens = [t.strip() for t in re.split(r'[/:\-]', cleaned) if t.strip()]
            ignored_tokens = {"IMPS", "P2A", "P2P", "CR", "DR"}
            for tok in reversed(tokens):
                u_tok = tok.upper()
                if u_tok not in ignored_tokens and len(tok) > 2:
                    if re.match(r'^[A-Z0-9]{5,18}$', u_tok) and any(c.isdigit() for c in u_tok):
                        continue
                    return tok.strip(), "IMPS"

        # 9. General Transfer / slash tokens
        tokens = [t.strip() for t in cleaned.split('/') if t.strip()]
        if len(tokens) >= 2:
            last = tokens[-1]
            if not last.isdigit() and len(last) > 2:
                return last, "TRANSFER"

        return None, None
