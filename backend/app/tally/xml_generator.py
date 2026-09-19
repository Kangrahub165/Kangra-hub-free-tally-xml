import xml.sax.saxutils as saxutils
from decimal import Decimal
from typing import List, Optional, Union
from datetime import date
from app.transactions.model import CanonicalStatement, TransactionItem
from app.transactions.snapshot import FinalConversionSnapshot, FinalVoucherEntry
from app.core.exceptions import XMLGenerationException

def escape_xml(text: Optional[str]) -> str:
    """Safely escapes XML characters &, <, >, ", '."""
    if not text:
        return ""
    return saxutils.escape(str(text), {'"': "&quot;", "'": "&apos;"})

def format_tally_date(d: Optional[date]) -> str:
    """Formats date to Tally's YYYYMMDD format."""
    if not d:
        return ""
    return d.strftime("%Y%m%d")

class TallyXMLGenerator:
    """
    Constructs import-ready Tally XML exactly matching Tally Prime / Tally 9 specifications.
    Strictly conforms to double-entry accounting with algebraic balancing.
    Consumes FinalConversionSnapshot as pure read-only input.
    """

    def __init__(self, default_bank_ledger: str = "Bank Account", default_cash_ledger: str = "Cash"):
        self.default_bank_ledger = default_bank_ledger
        self.default_cash_ledger = default_cash_ledger

    def generate_xml(
        self,
        statement: Union[FinalConversionSnapshot, CanonicalStatement],
        bank_ledger_name: Optional[str] = None,
        cash_ledger_name: Optional[str] = None
    ) -> str:
        # Normalize input to FinalConversionSnapshot if CanonicalStatement was passed
        if isinstance(statement, FinalConversionSnapshot):
            snapshot = statement
        elif isinstance(statement, CanonicalStatement):
            b_name = bank_ledger_name or statement.bank_ledger_name or self.default_bank_ledger
            c_name = cash_ledger_name or statement.cash_ledger_name or self.default_cash_ledger
            snapshot = FinalConversionSnapshot.create_from_statement(
                statement=statement,
                bank_ledger_name=b_name,
                cash_ledger_name=c_name
            )
        else:
            raise XMLGenerationException("Invalid data provided to TallyXMLGenerator.")

        bank_ledger = bank_ledger_name if (bank_ledger_name and bank_ledger_name.strip()) else snapshot.bank_ledger_name
        cash_ledger = cash_ledger_name if (cash_ledger_name and cash_ledger_name.strip()) else snapshot.cash_ledger_name
        
        escaped_bank = escape_xml(bank_ledger)
        escaped_cash = escape_xml(cash_ledger)

        # Build XML header
        lines: List[str] = [
            '<?xml version="1.0" encoding="utf-8"?>',
            '<ENVELOPE>',
            '    <HEADER>',
            '        <TALLYREQUEST>Import Data</TALLYREQUEST>',
            '    </HEADER>',
            '    <BODY>',
            '        <IMPORTDATA>',
            '            <REQUESTDESC>',
            '                <REPORTNAME>All Masters</REPORTNAME>',
            '            </REQUESTDESC>',
            '            <REQUESTDATA>'
        ]

        if not snapshot.transactions:
            raise XMLGenerationException("No transactions available to generate Tally XML.")

        for tx in snapshot.transactions:
            # 1. Determine effective amount and voucher type
            tally_date = format_tally_date(tx.date)
            vch_type = tx.voucher_type or "Payment"
            raw_narr = tx.narration or getattr(tx, "original_narration", "") or ""
            narration = escape_xml(raw_narr)
            party_ledger = escape_xml(tx.ledger_name)

            amount = tx.debit if tx.debit > Decimal("0.00") else tx.credit
            if amount == Decimal("0.00"):
                continue

            # Format amount string: standard number with 2 decimal places
            amt_str = f"{amount:.2f}".rstrip('0').rstrip('.') if '.' in f"{amount:.2f}" else f"{amount}"
            neg_amt_str = f"-{amt_str}"

            # Cheque / Instrument number
            inst_no = tx.instrument_number or tx.cheque_number
            ref_no = tx.reference or inst_no

            lines.append('                <TALLYMESSAGE xmlns:UDF="TallyUDF">')
            lines.append(f'                    <VOUCHER VCHTYPE="{vch_type}" ACTION="Create" OBJVIEW="Accounting Voucher View">')
            lines.append(f'                        <DATE>{tally_date}</DATE>')
            lines.append(f'                        <VOUCHERTYPENAME>{vch_type}</VOUCHERTYPENAME>')
            lines.append(f'                        <VOUCHERNUMBER>{tx.row_index}</VOUCHERNUMBER>')
            
            if ref_no:
                lines.append(f'                        <REFERENCE>{escape_xml(ref_no)}</REFERENCE>')
                lines.append(f'                        <REFERENCEDATE>{tally_date}</REFERENCEDATE>')

            lines.append(f'                        <NARRATION>{narration}</NARRATION>')
            lines.append(f'                        <EFFECTIVEDATE>{tally_date}</EFFECTIVEDATE>')

            # Bank allocation snippet if instrument number is present
            bank_allocation = []
            if inst_no:
                inst_date_str = format_tally_date(tx.instrument_date) if tx.instrument_date else tally_date
                bank_allocation.append('                            <BANKALLOCATIONS.LIST>')
                bank_allocation.append(f'                                <DATE>{tally_date}</DATE>')
                bank_allocation.append(f'                                <INSTRUMENTDATE>{inst_date_str}</INSTRUMENTDATE>')
                bank_allocation.append('                                <TRANSACTIONTYPE>Cheque/DD</TRANSACTIONTYPE>')
                bank_allocation.append(f'                                <PAYMENTFAVOURING>{party_ledger}</PAYMENTFAVOURING>')
                bank_allocation.append(f'                                <INSTRUMENTNUMBER>{escape_xml(inst_no)}</INSTRUMENTNUMBER>')
                bank_allocation.append('                                <STATUS>Cheque</STATUS>')
                bank_allocation.append(f'                                <AMOUNT>{amt_str}</AMOUNT>')
                bank_allocation.append('                            </BANKALLOCATIONS.LIST>')

            # Ledger entries based on voucher type matching SAMPLE.xml
            if vch_type == "Payment":
                # Bank credited (ISDEEMEDPOSITIVE=No, positive amount)
                # Expense/Party debited (ISDEEMEDPOSITIVE=Yes, negative amount)
                lines.append('                        <ALLLEDGERENTRIES.LIST>')
                lines.append(f'                            <LEDGERNAME>{escaped_bank}</LEDGERNAME>')
                lines.append('                            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>')
                lines.append(f'                            <AMOUNT>{amt_str}</AMOUNT>')
                if bank_allocation:
                    lines.extend(bank_allocation)
                lines.append('                        </ALLLEDGERENTRIES.LIST>')
                lines.append('                        <ALLLEDGERENTRIES.LIST>')
                lines.append(f'                            <LEDGERNAME>{party_ledger}</LEDGERNAME>')
                lines.append('                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>')
                lines.append(f'                            <AMOUNT>{neg_amt_str}</AMOUNT>')
                lines.append('                        </ALLLEDGERENTRIES.LIST>')

            elif vch_type == "Receipt":
                # Party credited (ISDEEMEDPOSITIVE=No, positive amount)
                # Bank debited (ISDEEMEDPOSITIVE=Yes, negative amount)
                lines.append('                        <ALLLEDGERENTRIES.LIST>')
                lines.append(f'                            <LEDGERNAME>{party_ledger}</LEDGERNAME>')
                lines.append('                            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>')
                lines.append(f'                            <AMOUNT>{amt_str}</AMOUNT>')
                lines.append('                        </ALLLEDGERENTRIES.LIST>')
                lines.append('                        <ALLLEDGERENTRIES.LIST>')
                lines.append(f'                            <LEDGERNAME>{escaped_bank}</LEDGERNAME>')
                lines.append('                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>')
                lines.append(f'                            <AMOUNT>{neg_amt_str}</AMOUNT>')
                if bank_allocation:
                    lines.extend(bank_allocation)
                lines.append('                        </ALLLEDGERENTRIES.LIST>')

            elif vch_type == "Contra":
                # Internal transfer: Bank <-> Cash or Bank <-> Bank
                if tx.credit > Decimal("0.00"):
                    # Inflow to bank: Party/Cash credited, Bank debited
                    lines.append('                        <ALLLEDGERENTRIES.LIST>')
                    lines.append(f'                            <LEDGERNAME>{party_ledger}</LEDGERNAME>')
                    lines.append('                            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>')
                    lines.append(f'                            <AMOUNT>{amt_str}</AMOUNT>')
                    lines.append('                        </ALLLEDGERENTRIES.LIST>')
                    lines.append('                        <ALLLEDGERENTRIES.LIST>')
                    lines.append(f'                            <LEDGERNAME>{escaped_bank}</LEDGERNAME>')
                    lines.append('                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>')
                    lines.append(f'                            <AMOUNT>{neg_amt_str}</AMOUNT>')
                    if bank_allocation:
                        lines.extend(bank_allocation)
                    lines.append('                        </ALLLEDGERENTRIES.LIST>')
                else:
                    # Outflow from bank: Bank credited, Party/Cash debited
                    lines.append('                        <ALLLEDGERENTRIES.LIST>')
                    lines.append(f'                            <LEDGERNAME>{escaped_bank}</LEDGERNAME>')
                    lines.append('                            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>')
                    lines.append(f'                            <AMOUNT>{amt_str}</AMOUNT>')
                    if bank_allocation:
                        lines.extend(bank_allocation)
                    lines.append('                        </ALLLEDGERENTRIES.LIST>')
                    lines.append('                        <ALLLEDGERENTRIES.LIST>')
                    lines.append(f'                            <LEDGERNAME>{party_ledger}</LEDGERNAME>')
                    lines.append('                            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>')
                    lines.append(f'                            <AMOUNT>{neg_amt_str}</AMOUNT>')
                    lines.append('                        </ALLLEDGERENTRIES.LIST>')

            lines.append('                    </VOUCHER>')
            lines.append('                </TALLYMESSAGE>')

        # Close XML structure
        lines.append('            </REQUESTDATA>')
        lines.append('        </IMPORTDATA>')
        lines.append('    </BODY>')
        lines.append('</ENVELOPE>')

        return "\n".join(lines)
