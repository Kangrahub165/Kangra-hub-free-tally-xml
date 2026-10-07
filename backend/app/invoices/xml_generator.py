import html
import xml.sax.saxutils as saxutils
from decimal import Decimal
from typing import List, Optional, Set, Dict, Any, Tuple
from uuid import uuid4
from datetime import date

from app.invoices.model import (
    InvoiceDocument,
    FinalInvoiceSnapshot,
    LedgerMappingConfig,
    InvoiceItem
)
from app.invoices.table_engine import (
    build_rate_details,
    rate_details_xml,
    reconcile,
    spread_paise
)

from app.accounting.tally_master_generator import (
    StockItemDraft,
    LedgerDraft,
    generate_stock_item_master_xml,
    verify_stock_item_round_trip,
    generate_ledger_master_xml,
    verify_ledger_round_trip,
    generate_unit_master_xml,
    verify_unit_round_trip,
    generate_stock_group_master_xml,
    extract_pan_from_gstin,
    MasterRoundTripMismatchError
)

def escape_xml(text: Optional[str]) -> str:
    """Escapes XML entities (&, <, >, \", ')."""
    if not text:
        return ""
    return saxutils.escape(str(text), {'"': "&quot;", "'": "&apos;"})

from datetime import datetime

def format_tally_date(d: Any) -> str:
    """Formats date to Tally standard YYYYMMDD."""
    if not d:
        return date.today().strftime("%Y%m%d")
    if isinstance(d, (date, datetime)):
        return d.strftime("%Y%m%d")
    d_str = str(d).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(d_str, fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    return date.today().strftime("%Y%m%d")

def is_intra_state(inv: InvoiceDocument) -> bool:
    """
    Determines if invoice is intra-state (Central + State Tax) or inter-state (Integrated Tax).
    Compares normalized 2-digit state codes (PRD Addendum 1 Section 1.7).
    """
    from app.invoices.state_normalizer import normalize_state, are_states_intra_state
    _, s_code = normalize_state(inv.supplier.state or (inv.supplier.gstin[:2] if inv.supplier.gstin else None))
    _, b_code = normalize_state(inv.buyer.state or (inv.buyer.gstin[:2] if inv.buyer.gstin else None) or inv.place_of_supply)

    if s_code and b_code:
        return are_states_intra_state(s_code, b_code)

    if inv.cgst_total > Decimal("0.00") or inv.sgst_total > Decimal("0.00"):
        return True
    if inv.igst_total > Decimal("0.00"):
        return False

    return True

class InvoiceTallyXMLGenerator:
    """
    Authoritative Tally XML Generator for Sales & Purchase Invoices.
    Strictly conforms to PURCHASE SAMPLE.xml and SALES SAMPLE.xml.
    Takes FinalInvoiceSnapshot as pure read-only authoritative input.
    """

    def generate_xml(self, snapshot: FinalInvoiceSnapshot) -> str:
        # PRD Addendum 6 Section 3.4: Unsaved master edits block XML generation
        if getattr(snapshot, "has_unsaved_master_edits", False):
            raise ValueError("You have unsaved changes. Please save all Create Master edits before generating XML.")

        mapping = snapshot.ledger_mapping
        raw_company = snapshot.company_name or "Kartar Singh & Sons - (from 1-Apr-25)"
        company_name = html.unescape(raw_company)

        lines: List[str] = [
            '<ENVELOPE>',
            ' <HEADER>',
            '  <TALLYREQUEST>Import Data</TALLYREQUEST>',
            ' </HEADER>',
            ' <BODY>',
            '  <IMPORTDATA>',
            '   <REQUESTDESC>',
            '    <REPORTNAME>All Masters</REPORTNAME>',
            '    <STATICVARIABLES>',
            f'     <SVCURRENTCOMPANY>{escape_xml(company_name)}</SVCURRENTCOMPANY>',
            '    </STATICVARIABLES>',
            '   </REQUESTDESC>',
            '   <REQUESTDATA>'
        ]

        # 1. Master Auto-Creation (Units, Stock Items, Party Ledgers)
        if snapshot.auto_create_items or snapshot.auto_create_parties:
            master_lines = self._generate_masters(snapshot)
            lines.extend(master_lines)

        # 2. Vouchers
        for idx, inv in enumerate(snapshot.invoices):
            raw_vch = (inv.invoice_number or "").strip()
            if not raw_vch or raw_vch in ("?", "UNKNOWN", "NONE", "null"):
                fallback_vch = f"INV-{idx + 1}"
            else:
                fallback_vch = raw_vch

            vch_num = (
                str(snapshot.starting_voucher_number + idx)
                if snapshot.voucher_numbering_mode == "SEQUENTIAL"
                else fallback_vch
            )

            if inv.invoice_type == "PURCHASE":
                v_lines = self._generate_purchase_voucher(inv, vch_num, mapping)
            else:
                v_lines = self._generate_sales_voucher(inv, vch_num, mapping)

            lines.extend(v_lines)

        lines.extend([
            '   </REQUESTDATA>',
            '  </IMPORTDATA>',
            ' </BODY>',
            '</ENVELOPE>'
        ])

        return "\n".join(lines)

    def _generate_masters(self, snapshot: FinalInvoiceSnapshot) -> List[str]:
        # PRD Section 10.1 Import Order: 1. Units -> 2. Groups -> 3. Ledgers -> 4. Stock Items -> 5. Vouchers
        unit_lines: List[str] = []
        group_lines: List[str] = []
        ledger_lines: List[str] = []
        stock_lines: List[str] = []

        created_units: Set[str] = set()
        created_groups: Set[str] = set()
        created_items: Set[str] = set()
        created_parties: Set[str] = set()

        UQC_MAPPING = {
            "BAG": "BAG-BAGS", "BAGS": "BAG-BAGS", "BOX": "BOX-BOX", "BOXES": "BOX-BOX",
            "BTL": "BTL-BOTTLES", "BOTTLE": "BTL-BOTTLES", "BOTTLES": "BTL-BOTTLES",
            "CAN": "PCS-PIECES", "CANS": "PCS-PIECES", "CASE": "PCS-PIECES", "CASES": "PCS-PIECES",
            "CRATE": "BOX-BOX", "CTN": "CTN-CARTONS", "CARTON": "CTN-CARTONS", "CARTONS": "CTN-CARTONS",
            "DOZ": "DOZ-DOZENS", "DOZEN": "DOZ-DOZENS", "DZN": "DOZ-DOZENS", "GM": "GMS-GRAMMES",
            "GMS": "GMS-GRAMMES", "KG": "KGS-KILOGRAMS", "KGS": "KGS-KILOGRAMS", "LTR": "LTR-LITRES",
            "LTRS": "LTR-LITRES", "ML": "MLT-MILILITRE", "MLT": "MLT-MILILITRE", "MTR": "MTR-METERS",
            "NOS": "NOS-NUMBERS", "PAC": "PAC-PACKS", "PACK": "PAC-PACKS", "PACKS": "PAC-PACKS",
            "PCS": "PCS-PIECES", "PIECES": "PCS-PIECES", "PKT": "PAC-PACKS", "POUCH": "PCS-PIECES",
            "SET": "SET-SETS", "SETS": "SET-SETS", "TIN": "PCS-PIECES", "UNT": "UNT-UNITS",
        }

        for inv in snapshot.invoices:
            # 1. Units of Measure (missing only)
            if snapshot.auto_create_items:
                for it in inv.items:
                    uoms_to_create = set()
                    uom_clean = (it.tally_uom or it.uom or "NOS").strip()
                    if uom_clean:
                        uoms_to_create.add(uom_clean)
                    alt_clean = (it.alternate_uom or it.uom_option_a or "").strip()
                    if alt_clean:
                        uoms_to_create.add(alt_clean)
                    opt_b_clean = (it.uom_option_b or "").strip()
                    if opt_b_clean:
                        uoms_to_create.add(opt_b_clean)

                    for u in uoms_to_create:
                        if u and u not in created_units:
                            created_units.add(u)
                            xml_u = generate_unit_master_xml(u)
                            verify_unit_round_trip(u, xml_u)
                            unit_lines.append(xml_u)

            # 2. Stock Groups (PRD Addendum 5: Auto-create any non-Primary groups)
            if snapshot.auto_create_items:
                for it in inv.items:
                    grp = (getattr(it, "parent_group", None) or "Primary").strip()
                    if grp and grp != "Primary" and grp not in created_groups:
                        created_groups.add(grp)
                        group_lines.append(generate_stock_group_master_xml(grp, "Primary"))

            # 3. Party Ledgers
            if snapshot.auto_create_parties:
                party = inv.supplier if inv.invoice_type == "PURCHASE" else inv.buyer
                p_name = (party.name or "").strip()
                if p_name and p_name not in created_parties and party.requires_ledger_creation:
                    created_parties.add(p_name)
                    parent_grp = getattr(party, "parent_group", None) or ("Sundry Creditors" if inv.invoice_type == "PURCHASE" else "Sundry Debtors")
                    ledger_lines.extend(self._generate_party_ledger_master(party, parent_grp))

            # 4. Stock Items
            if snapshot.auto_create_items:
                for it in inv.items:
                    uom_clean = (it.tally_uom or it.uom or "NOS").strip()
                    item_clean = (it.matched_stock_item or it.item_name or "").strip()
                    if item_clean and item_clean not in created_items and it.requires_item_creation:
                        created_items.add(item_clean)
                        stock_lines.extend(self._generate_stock_item_master(it, uom_clean))

        return unit_lines + group_lines + ledger_lines + stock_lines

    def _generate_stock_item_master(self, item: InvoiceItem, uom: str) -> List[str]:
        tot_rate = item.igst_rate if item.igst_rate > Decimal("0.00") else (item.cgst_rate + item.sgst_rate)
        base_uom = uom
        alt_uom = (item.alternate_uom or item.uom_option_a or "").strip()
        conv = item.pack_multiplier

        if item.is_converted_to_pieces and item.alternate_uom:
            base_uom = uom
            alt_uom = item.alternate_uom
        elif not item.is_converted_to_pieces and item.uom_option_b and conv and conv > Decimal("1"):
            base_uom = item.uom_option_b
            alt_uom = uom

        name_clean = (item.matched_stock_item or item.item_name or "").strip()
        conv_val = int(conv) if conv and conv >= 1 else None

        draft = StockItemDraft(
            name=name_clean,
            parent_group=getattr(item, "parent_group", None) or "Primary",
            base_unit=base_uom,
            alternate_unit=alt_uom if (alt_uom and conv and conv >= 1 and alt_uom != base_uom) else None,
            conversion=int(conv) if (alt_uom and conv and conv >= 1 and alt_uom != base_uom) else None,
            hsn_code=item.hsn_sac,
            hsn_description=getattr(item, "hsn_description", None),
            gst_rate=tot_rate,
            taxability=getattr(item, "taxability", None) or "Taxable",
            type_of_supply=getattr(item, "type_of_supply", None) or "Goods"
        )
        xml_str = generate_stock_item_master_xml(draft)
        verify_stock_item_round_trip(draft, xml_str)
        return [xml_str]

    def _generate_party_ledger_master(self, party: any, parent_group: str) -> List[str]:
        pan_val = getattr(party, "pan", None) or extract_pan_from_gstin(party.gstin)
        reg_type = getattr(party, "registration_type", None) or ("Regular" if party.gstin else "Unregistered/Consumer")
        pin = getattr(party, "pincode", None)
        if not pin and getattr(party, "address", None):
            m_pin = re.search(r'\b[1-9][0-9]{5}\b', party.address)
            if m_pin:
                pin = m_pin.group(0)

        addr_lines = [party.address.strip()] if getattr(party, "address", None) and party.address.strip() else []
        draft = LedgerDraft(
            name=party.name,
            alias=getattr(party, "alias", None),
            parent_group=getattr(party, "parent_group", None) or parent_group,
            address_lines=addr_lines,
            state=party.state or (party.gstin[:2] if party.gstin else None) or "Himachal Pradesh",
            country="India",
            pincode=pin,
            gstin=party.gstin,
            pan=pan_val,
            registration_type=reg_type
        )
        xml_str = generate_ledger_master_xml(draft)
        verify_ledger_round_trip(draft, xml_str)
        return [xml_str]

    def _generate_purchase_voucher(
        self,
        inv: InvoiceDocument,
        vch_num: str,
        mapping: LedgerMappingConfig
    ) -> List[str]:
        intra = is_intra_state(inv)

        # 1. Reconcile bill total vs computed total (Addendum 3)
        lines_data = []
        for it in inv.items:
            line_tax = it.cgst_amount + it.sgst_amount + it.igst_amount + (it.cess_amount if hasattr(it, 'cess_amount') else Decimal("0.00"))
            if line_tax == Decimal("0.00"):
                tot_rate = it.igst_rate if it.igst_rate > Decimal("0.00") else (it.cgst_rate + it.sgst_rate)
                if tot_rate > Decimal("0.00"):
                    line_tax = (it.taxable_amount * tot_rate / Decimal("100")).quantize(Decimal("0.01"))
            lines_data.append({"taxable": it.taxable_amount, "tax": line_tax})

        printed_tax_total = inv.cgst_total + inv.sgst_total + inv.igst_total + inv.cess_total
        if printed_tax_total > Decimal("0.00") and len(lines_data) > 0:
            spread_paise(lines_data, printed_tax_total)

        other_charges_val = inv.other_charges or Decimal("0.00")
        discount_val = inv.discount_total or Decimal("0.00")
        rec_result = reconcile(
            lines=lines_data,
            printed_total=inv.grand_total,
            other_charges=other_charges_val,
            discount=discount_val,
            printed_round_off=inv.round_off if inv.round_off != Decimal("0.00") else None
        )
        if discount_val == Decimal("0.00") and rec_result["status"] == "DISCOUNT_EXPLAINED":
            discount_val = rec_result["discount"]

        guid = inv.id or str(uuid4())
        d_str = format_tally_date(inv.invoice_date)
        party_ledger = (inv.supplier.matched_ledger_name or inv.supplier.name or "").strip() or "Supplier"
        party_gstin = inv.supplier.gstin or ""
        from app.invoices.state_normalizer import normalize_state
        state_name, _ = normalize_state(inv.supplier.state or (inv.supplier.gstin[:2] if inv.supplier.gstin else None))
        pos, _ = normalize_state(inv.place_of_supply or inv.buyer.state or (inv.buyer.gstin[:2] if inv.buyer.gstin else None))
        state_name = state_name or "Himachal Pradesh"
        pos = pos or state_name
        ref_no = inv.invoice_number or vch_num
        narr = inv.narration or f"Purchased from {party_ledger} against Invoice No. {ref_no}."

        lines = [
            '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
            f'     <VOUCHER REMOTEID="{guid}" VCHKEY="{guid}:00000040" VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">',
            f'      <DATE>{d_str}</DATE>',
            f'      <REFERENCEDATE>{d_str}</REFERENCEDATE>',
            f'      <VCHSTATUSDATE>{d_str}</VCHSTATUSDATE>',
            f'      <GUID>{guid}</GUID>',
            '      <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>',
            f'      <STATENAME>{escape_xml(state_name)}</STATENAME>',
            f'      <NARRATION>{escape_xml(narr)}</NARRATION>',
            '      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>',
            f'      <PARTYGSTIN>{escape_xml(party_gstin)}</PARTYGSTIN>',
            f'      <PLACEOFSUPPLY>{escape_xml(pos)}</PLACEOFSUPPLY>',
            '      <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>',
            f'      <PARTYNAME>{escape_xml(party_ledger)}</PARTYNAME>',
            f'      <PARTYLEDGERNAME>{escape_xml(party_ledger)}</PARTYLEDGERNAME>',
            f'      <VOUCHERNUMBER>{escape_xml(vch_num)}</VOUCHERNUMBER>',
            f'      <REFERENCE>{escape_xml(ref_no)}</REFERENCE>',
            f'      <PARTYMAILINGNAME>{escape_xml(party_ledger)}</PARTYMAILINGNAME>',
            '      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>',
            '      <VCHENTRYMODE>Item Invoice</VCHENTRYMODE>',
            '      <ISINVOICE>Yes</ISINVOICE>',
            '      <ISELIGIBLEFORITC>Yes</ISELIGIBLEFORITC>'
        ]

        # ALLINVENTORYENTRIES.LIST
        for it in inv.items:
            it_name = it.matched_stock_item or it.item_name or "Stock Item"
            rate_val = it.rate if it.rate > Decimal("0.00") else (it.taxable_amount / it.quantity if it.quantity > 0 else it.taxable_amount)
            taxable_neg = -abs(it.taxable_amount)
            final_uom = (it.tally_uom or it.uom or "NOS").strip()
            mult = it.pack_multiplier or Decimal("1")
            actual_qty_val = (it.shipped_qty * mult) if it.shipped_qty is not None else it.quantity
            billed_qty_val = it.quantity

            lines.extend([
                '      <ALLINVENTORYENTRIES.LIST>',
                f'       <STOCKITEMNAME>{escape_xml(it_name)}</STOCKITEMNAME>',
                '       <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>',
                '       <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>',
                f'       <GSTHSNNAME>{escape_xml(it.hsn_sac or "9999")}</GSTHSNNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <RATE>{rate_val:.2f}/{escape_xml(final_uom)}</RATE>',
                f'       <AMOUNT>{taxable_neg:.2f}</AMOUNT>',
                f'       <ACTUALQTY> {actual_qty_val:.3f} {escape_xml(final_uom)}</ACTUALQTY>',
                f'       <BILLEDQTY> {billed_qty_val:.3f} {escape_xml(final_uom)}</BILLEDQTY>',
                '       <BATCHALLOCATIONS.LIST>',
                '        <GODOWNNAME>Main Location</GODOWNNAME>',
                '        <BATCHNAME>Primary Batch</BATCHNAME>',
                f'        <AMOUNT>{taxable_neg:.2f}</AMOUNT>',
                f'        <ACTUALQTY> {actual_qty_val:.3f} {escape_xml(final_uom)}</ACTUALQTY>',
                f'        <BILLEDQTY> {billed_qty_val:.3f} {escape_xml(final_uom)}</BILLEDQTY>',
                '       </BATCHALLOCATIONS.LIST>',
                '       <ACCOUNTINGALLOCATIONS.LIST>',
                f'        <LEDGERNAME>{escape_xml(mapping.purchase_ledger)}</LEDGERNAME>',
                '        <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>',
                '        <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'        <AMOUNT>{taxable_neg:.2f}</AMOUNT>',
                '       </ACCOUNTINGALLOCATIONS.LIST>'
            ])

            # Authoritative GST rate from the bill line item (Addendum 2 & 3)
            tot_rate = it.igst_rate if it.igst_rate > Decimal("0.00") else (it.cgst_rate + it.sgst_rate)
            if tot_rate == Decimal("0.00"):
                line_tax = it.cgst_amount + it.sgst_amount + it.igst_amount
                if line_tax > Decimal("0.00") and it.taxable_amount > Decimal("0.00"):
                    tot_rate = (line_tax * Decimal("100") / it.taxable_amount).quantize(Decimal("0.01"))

            if tot_rate > Decimal("0.00"):
                cess_val = it.cess_rate if hasattr(it, 'cess_rate') else None
                rate_pairs = build_rate_details(tot_rate, intra_state=intra, cess_rate=cess_val)
                lines.extend(rate_details_xml(rate_pairs))

            lines.append('      </ALLINVENTORYENTRIES.LIST>')

        # LEDGERENTRIES.LIST
        # 1. Supplier / Party (Credit -> Positive amount in Tally purchase)
        lines.extend([
            '      <LEDGERENTRIES.LIST>',
            f'       <LEDGERNAME>{escape_xml(party_ledger)}</LEDGERNAME>',
            '       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
            '       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>',
            f'       <AMOUNT>{abs(inv.grand_total):.2f}</AMOUNT>',
            '      </LEDGERENTRIES.LIST>'
        ])

        # 2. CGST (Debit -> Negative amount in Tally purchase)
        if inv.cgst_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.cgst_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>-{abs(inv.cgst_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 3. SGST (Debit -> Negative amount in Tally purchase)
        if inv.sgst_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.sgst_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>-{abs(inv.sgst_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 4. IGST (Debit -> Negative amount in Tally purchase)
        if inv.igst_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.igst_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>-{abs(inv.igst_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 5. Cess
        if inv.cess_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.cess_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>-{abs(inv.cess_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 6. Other Charges
        other_sum = inv.other_charges or Decimal("0.00")
        if abs(other_sum) >= Decimal("0.005"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.other_charges_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>-{abs(other_sum):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 7. Discount / Scheme (PRD Addendum 2 Part C & Golden Rules)
        # Only emit discount ledger entry if voucher items are gross and reduced to net,
        # OR if it is a post-tax discount under Pattern 4.
        # If line items are ALREADY net (P1, P2, P3, P5, P6, P7), DO NOT emit discount ledger (prevents double discount).
        emit_discount_ledger = False
        discount_in_voucher = Decimal("0.00")

        if inv.discount_pattern == "P4_POST_TAX_DISCOUNT" or (inv.post_tax_discount and inv.post_tax_discount > Decimal("0.00")):
            emit_discount_ledger = True
            discount_in_voucher = inv.post_tax_discount if (inv.post_tax_discount and inv.post_tax_discount > Decimal("0.00")) else discount_val
        elif inv.discount_pattern in ("P1_ALREADY_NET", "P2_LINE_DISCOUNT_SUBTRACTED", "P3_BOTTOM_DISCOUNT_SPREAD", "P5_RATE_ALREADY_NET", "P6_TWO_DISCOUNTS_SEQUENTIAL", "P7_FREE_GOODS"):
            emit_discount_ledger = False
            discount_in_voucher = Decimal("0.00")
        elif abs(discount_val) >= Decimal("0.005"):
            taxable_sum_check = sum((it.taxable_amount for it in inv.items), Decimal("0.00"))
            tax_sum_check = inv.cgst_total + inv.sgst_total + inv.igst_total + inv.cess_total
            if abs((taxable_sum_check + tax_sum_check + other_sum) - inv.grand_total) <= Decimal("1.00"):
                emit_discount_ledger = False
                discount_in_voucher = Decimal("0.00")
            else:
                emit_discount_ledger = True
                discount_in_voucher = discount_val

        if emit_discount_ledger and abs(discount_in_voucher) >= Decimal("0.005"):
            disc_name = mapping.discount_ledger or "Discount"
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(disc_name)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>-{abs(discount_in_voucher):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 8. Round Off
        taxable_sum = sum((it.taxable_amount for it in inv.items), Decimal("0.00"))
        tax_sum = inv.cgst_total + inv.sgst_total + inv.igst_total + inv.cess_total
        ro_delta = inv.grand_total - (taxable_sum + tax_sum + other_sum + (discount_in_voucher if emit_discount_ledger else Decimal("0.00")))
        if abs(ro_delta) >= Decimal("0.005"):
            ro_amt = -ro_delta
            ro_pos = "Yes" if ro_amt <= Decimal("0.00") else "No"
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.round_off_ledger)}</LEDGERNAME>',
                f'       <ISDEEMEDPOSITIVE>{ro_pos}</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>{ro_amt:.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        lines.extend([
            '     </VOUCHER>',
            '    </TALLYMESSAGE>'
        ])
        return lines

    def _generate_sales_voucher(
        self,
        inv: InvoiceDocument,
        vch_num: str,
        mapping: LedgerMappingConfig
    ) -> List[str]:
        intra = is_intra_state(inv)

        # 1. Reconcile bill total vs computed total (Addendum 3)
        lines_data = []
        for it in inv.items:
            line_tax = it.cgst_amount + it.sgst_amount + it.igst_amount + (it.cess_amount if hasattr(it, 'cess_amount') else Decimal("0.00"))
            if line_tax == Decimal("0.00"):
                tot_rate = it.igst_rate if it.igst_rate > Decimal("0.00") else (it.cgst_rate + it.sgst_rate)
                if tot_rate > Decimal("0.00"):
                    line_tax = (it.taxable_amount * tot_rate / Decimal("100")).quantize(Decimal("0.01"))
            lines_data.append({"taxable": it.taxable_amount, "tax": line_tax})

        printed_tax_total = inv.cgst_total + inv.sgst_total + inv.igst_total + inv.cess_total
        if printed_tax_total > Decimal("0.00") and len(lines_data) > 0:
            spread_paise(lines_data, printed_tax_total)

        other_charges_val = inv.other_charges or Decimal("0.00")
        discount_val = inv.discount_total or Decimal("0.00")
        rec_result = reconcile(
            lines=lines_data,
            printed_total=inv.grand_total,
            other_charges=other_charges_val,
            discount=discount_val,
            printed_round_off=inv.round_off if inv.round_off != Decimal("0.00") else None
        )
        if discount_val == Decimal("0.00") and rec_result["status"] == "DISCOUNT_EXPLAINED":
            discount_val = rec_result["discount"]

        guid = inv.id or str(uuid4())
        d_str = format_tally_date(inv.invoice_date)
        customer_ledger = (inv.buyer.matched_ledger_name or inv.buyer.name or "").strip() or "Customer"
        from app.invoices.state_normalizer import normalize_state
        state_name, _ = normalize_state(inv.buyer.state or (inv.buyer.gstin[:2] if inv.buyer.gstin else None))
        pos, _ = normalize_state(inv.place_of_supply or state_name)
        state_name = state_name or "Himachal Pradesh"
        pos = pos or state_name
        narr = inv.narration or f"Sales to {customer_ledger} against Invoice No. {vch_num}."

        lines = [
            '    <TALLYMESSAGE xmlns:UDF="TallyUDF">',
            f'     <VOUCHER REMOTEID="{guid}" VCHKEY="{guid}:00000008" VCHTYPE="Sales" ACTION="Create" OBJVIEW="Invoice Voucher View">',
            f'      <DATE>{d_str}</DATE>',
            f'      <VCHSTATUSDATE>{d_str}</VCHSTATUSDATE>',
            f'      <GUID>{guid}</GUID>',
            f'      <GSTREGISTRATIONTYPE>{"Regular" if inv.buyer.gstin else "Unregistered/Consumer"}</GSTREGISTRATIONTYPE>',
            f'      <STATENAME>{escape_xml(state_name)}</STATENAME>',
            f'      <NARRATION>{escape_xml(narr)}</NARRATION>',
            '      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>',
            f'      <PLACEOFSUPPLY>{escape_xml(pos)}</PLACEOFSUPPLY>',
            '      <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>',
            f'      <PARTYNAME>{escape_xml(customer_ledger)}</PARTYNAME>',
            f'      <PARTYLEDGERNAME>{escape_xml(customer_ledger)}</PARTYLEDGERNAME>',
            f'      <VOUCHERNUMBER>{escape_xml(vch_num)}</VOUCHERNUMBER>',
            f'      <BASICBUYERNAME>{escape_xml(customer_ledger)}</BASICBUYERNAME>',
            f'      <PARTYMAILINGNAME>{escape_xml(customer_ledger)}</PARTYMAILINGNAME>',
            f'      <CONSIGNEEMAILINGNAME>{escape_xml(customer_ledger)}</CONSIGNEEMAILINGNAME>',
            f'      <CONSIGNEESTATENAME>{escape_xml(state_name)}</CONSIGNEESTATENAME>',
            '      <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>',
            '      <VCHENTRYMODE>Item Invoice</VCHENTRYMODE>',
            '      <ISINVOICE>Yes</ISINVOICE>'
        ]

        # ALLINVENTORYENTRIES.LIST
        for it in inv.items:
            it_name = it.matched_stock_item or it.item_name or "Stock Item"
            rate_val = it.rate if it.rate > Decimal("0.00") else (it.taxable_amount / it.quantity if it.quantity > 0 else it.taxable_amount)
            taxable_pos = abs(it.taxable_amount)
            final_uom = (it.tally_uom or it.uom or "NOS").strip()
            mult = it.pack_multiplier or Decimal("1")
            actual_qty_val = (it.shipped_qty * mult) if it.shipped_qty is not None else it.quantity
            billed_qty_val = it.quantity

            lines.extend([
                '      <ALLINVENTORYENTRIES.LIST>',
                f'       <STOCKITEMNAME>{escape_xml(it_name)}</STOCKITEMNAME>',
                '       <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>',
                '       <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>',
                f'       <GSTHSNNAME>{escape_xml(it.hsn_sac or "9999")}</GSTHSNNAME>',
                '       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'       <RATE>{rate_val:.2f}/{escape_xml(final_uom)}</RATE>',
                f'       <AMOUNT>{taxable_pos:.2f}</AMOUNT>',
                f'       <ACTUALQTY> {actual_qty_val:.3f} {escape_xml(final_uom)}</ACTUALQTY>',
                f'       <BILLEDQTY> {billed_qty_val:.3f} {escape_xml(final_uom)}</BILLEDQTY>',
                '       <BATCHALLOCATIONS.LIST>',
                '        <GODOWNNAME>Main Location</GODOWNNAME>',
                '        <BATCHNAME>Primary Batch</BATCHNAME>',
                f'        <AMOUNT>{taxable_pos:.2f}</AMOUNT>',
                f'        <ACTUALQTY> {actual_qty_val:.3f} {escape_xml(final_uom)}</ACTUALQTY>',
                f'        <BILLEDQTY> {billed_qty_val:.3f} {escape_xml(final_uom)}</BILLEDQTY>',
                '       </BATCHALLOCATIONS.LIST>',
                '       <ACCOUNTINGALLOCATIONS.LIST>',
                f'        <LEDGERNAME>{escape_xml(mapping.sales_ledger)}</LEDGERNAME>',
                '        <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'        <AMOUNT>{taxable_pos:.2f}</AMOUNT>',
                '       </ACCOUNTINGALLOCATIONS.LIST>'
            ])

            # Authoritative GST rate from the bill line item (Addendum 2 & 3)
            tot_rate = it.igst_rate if it.igst_rate > Decimal("0.00") else (it.cgst_rate + it.sgst_rate)
            if tot_rate == Decimal("0.00"):
                line_tax = it.cgst_amount + it.sgst_amount + it.igst_amount
                if line_tax > Decimal("0.00") and it.taxable_amount > Decimal("0.00"):
                    tot_rate = (line_tax * Decimal("100") / it.taxable_amount).quantize(Decimal("0.01"))

            if tot_rate > Decimal("0.00"):
                cess_val = it.cess_rate if hasattr(it, 'cess_rate') else None
                rate_pairs = build_rate_details(tot_rate, intra_state=intra, cess_rate=cess_val)
                lines.extend(rate_details_xml(rate_pairs))

            lines.append('      </ALLINVENTORYENTRIES.LIST>')

        # LEDGERENTRIES.LIST
        # 1. Customer (Debit -> Negative amount in Tally sales)
        lines.extend([
            '      <LEDGERENTRIES.LIST>',
            f'       <LEDGERNAME>{escape_xml(customer_ledger)}</LEDGERNAME>',
            '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
            '       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>',
            f'       <AMOUNT>-{abs(inv.grand_total):.2f}</AMOUNT>',
            '      </LEDGERENTRIES.LIST>'
        ])

        # 2. CGST (Credit -> Positive amount in Tally sales)
        if inv.cgst_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.cgst_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>{abs(inv.cgst_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 3. SGST (Credit -> Positive amount in Tally sales)
        if inv.sgst_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.sgst_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>{abs(inv.sgst_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 4. IGST (Credit -> Positive amount in Tally sales)
        if inv.igst_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.igst_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>{abs(inv.igst_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 5. Cess
        if inv.cess_total > Decimal("0.00"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.cess_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>{abs(inv.cess_total):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 6. Other Charges
        other_sum = inv.other_charges or Decimal("0.00")
        if abs(other_sum) >= Decimal("0.005"):
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.other_charges_ledger)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>{abs(other_sum):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 7. Discount Allowed (PRD Addendum 2 Part C & Golden Rules)
        # Only emit discount ledger entry if voucher items are gross and reduced to net,
        # OR if it is a post-tax discount under Pattern 4.
        # If line items are ALREADY net (P1, P2, P3, P5, P6, P7), DO NOT emit discount ledger (prevents double discount).
        emit_discount_ledger = False
        discount_in_voucher = Decimal("0.00")

        if inv.discount_pattern == "P4_POST_TAX_DISCOUNT" or (inv.post_tax_discount and inv.post_tax_discount > Decimal("0.00")):
            emit_discount_ledger = True
            discount_in_voucher = inv.post_tax_discount if (inv.post_tax_discount and inv.post_tax_discount > Decimal("0.00")) else discount_val
        elif inv.discount_pattern in ("P1_ALREADY_NET", "P2_LINE_DISCOUNT_SUBTRACTED", "P3_BOTTOM_DISCOUNT_SPREAD", "P5_RATE_ALREADY_NET", "P6_TWO_DISCOUNTS_SEQUENTIAL", "P7_FREE_GOODS"):
            emit_discount_ledger = False
            discount_in_voucher = Decimal("0.00")
        elif abs(discount_val) >= Decimal("0.005"):
            taxable_sum_check = sum((it.taxable_amount for it in inv.items), Decimal("0.00"))
            tax_sum_check = inv.cgst_total + inv.sgst_total + inv.igst_total + inv.cess_total
            if abs((taxable_sum_check + tax_sum_check + other_sum) - inv.grand_total) <= Decimal("1.00"):
                emit_discount_ledger = False
                discount_in_voucher = Decimal("0.00")
            else:
                emit_discount_ledger = True
                discount_in_voucher = discount_val

        if emit_discount_ledger and abs(discount_in_voucher) >= Decimal("0.005"):
            disc_name = mapping.discount_ledger or "Discount"
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(disc_name)}</LEDGERNAME>',
                '       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>-{abs(discount_in_voucher):.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        # 8. Round Off
        taxable_sum = sum((it.taxable_amount for it in inv.items), Decimal("0.00"))
        tax_sum = inv.cgst_total + inv.sgst_total + inv.igst_total + inv.cess_total
        ro_delta = inv.grand_total - (taxable_sum + tax_sum + other_sum - (discount_in_voucher if emit_discount_ledger else Decimal("0.00")))
        if abs(ro_delta) >= Decimal("0.005"):
            ro_amt = ro_delta
            ro_pos = "No" if ro_amt >= Decimal("0.00") else "Yes"
            lines.extend([
                '      <LEDGERENTRIES.LIST>',
                f'       <LEDGERNAME>{escape_xml(mapping.round_off_ledger)}</LEDGERNAME>',
                f'       <ISDEEMEDPOSITIVE>{ro_pos}</ISDEEMEDPOSITIVE>',
                f'       <AMOUNT>{ro_amt:.2f}</AMOUNT>',
                '      </LEDGERENTRIES.LIST>'
            ])

        lines.extend([
            '     </VOUCHER>',
            '    </TALLYMESSAGE>'
        ])
        return lines
