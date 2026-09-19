import re
from typing import List, Dict, Any

# Precision signatures for all 38 supported Indian commercial banks.
# Signatures use strictly word-bounded regexes, exact account lengths,
# and distinct header markers to prevent cross-bank false positives.
BANK_SIGNATURES: List[Dict[str, Any]] = [
    {
        "bank_name": "State Bank of India (SBI)",
        "parser_key": "sbi_standard",
        "header_names": [
            r"\bSTATE\s+BANK\s+OF\s+INDIA\b",
            r"\bSTATE\s+BANK\b",
            r"\bSBI\b"
        ],
        "ifsc_prefix": "SBIN0",
        "domains": ["onlinesbi.sbi", "onlinesbi.com", "sbi.co.in"],
        "header_markers": [
            r"CIF\s+No\.?\s*:",
            r"Drawing\s+Power\s*:",
            r"Account\s+Description\s*:",
            r"Balance\s+as\s+on\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}",
            r"EB-MSME-CC",
            r"INB\s+Txn"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|A/c\s*No\.?)\s*[:\-]?\s*(?:\(cid:\d+\)\s*)?(000000[0-9]{11}|[0-9]{11})\b"
        ],
        "column_patterns": [
            r"Txn\s+Date.+Value\s+Date.+Description.+Ref\s+No\./Cheque\s+No\..+Branch\s+Code.+Debit.+Credit.+Balance",
            r"Date.+Particulars\s*/\s*Narration.+Chq/Ref\s+No.+Withdrawal\s*\(Dr\).+Deposit\s*\(Cr\).+Balance"
        ],
        "priority": 10
    },
    {
        "bank_name": "Punjab National Bank (PNB)",
        "parser_key": "pnb_standard",
        "header_names": [
            r"\bPUNJAB\s+NATIONAL\s+BANK\b",
            r"\bPNB\s+PARIVAR\b"
        ],
        "ifsc_prefix": "PUNB0",
        "domains": ["pnbindia.in", "netpnb.com", "pnbindia.com"],
        "header_markers": [
            r"Account\s+Statement\s+For\s+Account\s*:",
            r"Customer\s+ID\s*:",
            r"Scheme\s+Code\s*:",
            r"Nomination\s+Registered\s*:",
            r"Branch\s+Details",
            r"Statement\s+Period\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+(?:Number|No\.?)|For\s+Account)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [
            r"Post\s+Date.+Val\s+Date.+Particulars.+Cheque\s+No\..+Debit.+Credit.+Balance",
            r"Date.+Particulars.+Cheque\s+No\.?\.+Withdrawal.+Deposit.+Balance"
        ],
        "priority": 10
    },
    {
        "bank_name": "HDFC Bank",
        "parser_key": "hdfc_standard",
        "header_names": [
            r"\bHDFC\s+BANK\s+LIMITED\b",
            r"\bHDFC\s+BANK\b"
        ],
        "ifsc_prefix": "HDFC0",
        "domains": ["hdfcbank.com"],
        "header_markers": [
            r"Cust\s+ID\s*:",
            r"Account\s+Branch\s*:",
            r"RTGS/NEFT\s+IFSC\s*:\s*HDFC0"
        ],
        "account_patterns": [
            r"(?:Account\s+No\.?|A/c\s*No\.?)\s*[:\-]?\s*([0-9]{14})\b"
        ],
        "column_patterns": [
            r"Date.+Narration.+Chq\./Ref\s+No\..+Value\s+Dt.+Withdrawal\s+Amt\..+Deposit\s+Amt\..+Closing\s+Balance"
        ],
        "priority": 10
    },
    {
        "bank_name": "ICICI Bank",
        "parser_key": "icici_standard",
        "header_names": [
            r"\bICICI\s+BANK\s+LIMITED\b",
            r"\bICICI\s+BANK\b"
        ],
        "ifsc_prefix": "ICIC0",
        "domains": ["icicibank.com"],
        "header_markers": [
            r"Account\s+Title\s*:",
            r"Base\s+Branch\s*:",
            r"MICR\s+Code\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{12})\b"
        ],
        "column_patterns": [
            r"Transaction\s+Date.+Value\s+Date.+Cheque\s+Number.+Transaction\s+Remarks.+Withdrawal\s+Amount\s*\(INR\).+Deposit\s+Amount\s*\(INR\).+Balance\s*\(INR\)"
        ],
        "priority": 10
    },
    {
        "bank_name": "Axis Bank",
        "parser_key": "axis_standard",
        "header_names": [
            r"\bAXIS\s+BANK\s+LTD\b",
            r"\bAXIS\s+BANK\b"
        ],
        "ifsc_prefix": "UTIB0",
        "domains": ["axisbank.com"],
        "header_markers": [
            r"Customer\s+ID\s*:",
            r"Branch\s+Name\s*:",
            r"IFSC\s*:\s*UTIB0"
        ],
        "account_patterns": [
            r"(?:Account\s+No\.?|A/c\s*No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [
            r"Tran\s+Date.+Value\s+Date.+Transaction\s+Particulars.+Chq\s+No.+Amount\s*\(INR\).+DR/CR.+Balance\s*\(INR\)"
        ],
        "priority": 10
    },
    {
        "bank_name": "Kotak Mahindra Bank",
        "parser_key": "kotak_standard",
        "header_names": [
            r"\bKOTAK\s+MAHINDRA\s+BANK\b",
            r"\bKOTAK\s+BANK\b"
        ],
        "ifsc_prefix": "KKBK0",
        "domains": ["kotak.com"],
        "header_markers": [
            r"CRN\s*:",
            r"Account\s+Entity\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,14})\b"
        ],
        "column_patterns": [],
        "priority": 10
    },
    {
        "bank_name": "Bank of Baroda (BOB)",
        "parser_key": "bob_standard",
        "header_names": [
            r"\bBANK\s+OF\s+BARODA\b",
            r"\bBARODA\s+CONNECT\b"
        ],
        "ifsc_prefix": "BARB0",
        "domains": ["bankofbaroda.in", "bankofbaroda.com"],
        "header_markers": [
            r"Customer\s+ID\s*:",
            r"Baroda\s+Connect"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b"
        ],
        "column_patterns": [],
        "priority": 10
    },
    {
        "bank_name": "IDFC FIRST Bank",
        "parser_key": "idfc_standard",
        "header_names": [
            r"\bIDFC\s+FIRST\s+BANK\b",
            r"\bIDFC\s+BANK\b"
        ],
        "ifsc_prefix": "IDFB0",
        "domains": ["idfcfirstbank.com"],
        "header_markers": [
            r"Customer\s+ID\s*:",
            r"IDFC\s+FIRST"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,14})\b"
        ],
        "column_patterns": [],
        "priority": 10
    },
    {
        "bank_name": "YES Bank",
        "parser_key": "yes_standard",
        "header_names": [
            r"\bYES\s+BANK\s+LTD\b",
            r"\bYES\s+BANK\b"
        ],
        "ifsc_prefix": "YESB0",
        "domains": ["yesbank.in"],
        "header_markers": [
            r"Cust\s+ID\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [],
        "priority": 10
    },
    {
        "bank_name": "RBL Bank",
        "parser_key": "rbl_standard",
        "header_names": [
            r"\bRBL\s+BANK\s+LIMITED\b",
            r"\bRBL\s+BANK\b",
            r"\bRATNAKAR\s+BANK\b"
        ],
        "ifsc_prefix": "RATN0",
        "domains": ["rblbank.com"],
        "header_markers": [
            r"CIF\s+ID\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,16})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "DCB Bank",
        "parser_key": "dcb_standard",
        "header_names": [
            r"\bDCB\s+BANK\s+LIMITED\b",
            r"\bDCB\s+BANK\b"
        ],
        "ifsc_prefix": "DCBL0",
        "domains": ["dcbbank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,16})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Union Bank of India",
        "parser_key": "union_standard",
        "header_names": [
            r"\bUNION\s+BANK\s+OF\s+INDIA\b"
        ],
        "ifsc_prefix": "UBIN0",
        "domains": ["unionbankofindia.co.in", "unionbankonline.co.in"],
        "header_markers": [
            r"Customer\s+ID\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Canara Bank",
        "parser_key": "canara_standard",
        "header_names": [
            r"\bCANARA\s+BANK\b"
        ],
        "ifsc_prefix": "CNRB0",
        "domains": ["canarabank.com"],
        "header_markers": [
            r"Customer\s+ID\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{13})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Indian Bank",
        "parser_key": "indian_standard",
        "header_names": [
            r"\bINDIAN\s+BANK\b"
        ],
        "ifsc_prefix": "IDIB0",
        "domains": ["indianbank.in"],
        "header_markers": [
            r"CIF\s+No\.?\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{9,17})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Indian Overseas Bank (IOB)",
        "parser_key": "iob_standard",
        "header_names": [
            r"\bINDIAN\s+OVERSEAS\s+BANK\b"
        ],
        "ifsc_prefix": "IOBA0",
        "domains": ["iob.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Bank of India (BOI)",
        "parser_key": "boi_standard",
        "header_names": [
            r"(?<!STATE\s)(?<!UNION\s)(?<!CENTRAL\s)\bBANK\s+OF\s+INDIA\b"
        ],
        "ifsc_prefix": "BKID0",
        "domains": ["bankofindia.co.in"],
        "header_markers": [
            r"Customer\s+No\.?\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Bank of Maharashtra",
        "parser_key": "maharashtra_standard",
        "header_names": [
            r"\bBANK\s+OF\s+MAHARASHTRA\b"
        ],
        "ifsc_prefix": "MAHB0",
        "domains": ["bankofmaharashtra.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{11})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Central Bank of India",
        "parser_key": "cbi_standard",
        "header_names": [
            r"\bCENTRAL\s+BANK\s+OF\s+INDIA\b"
        ],
        "ifsc_prefix": "CBIN0",
        "domains": ["centralbankofindia.co.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "UCO Bank",
        "parser_key": "uco_standard",
        "header_names": [
            r"\bUCO\s+BANK\b"
        ],
        "ifsc_prefix": "UCBA0",
        "domains": ["ucobank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Punjab & Sind Bank",
        "parser_key": "psb_standard",
        "header_names": [
            r"\bPUNJAB\s+(&|AND)\s+SIND\s+BANK\b"
        ],
        "ifsc_prefix": "PSIB0",
        "domains": ["punjabandsindbank.co.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "IndusInd Bank",
        "parser_key": "indusind_standard",
        "header_names": [
            r"\bINDUSIND\s+BANK\b"
        ],
        "ifsc_prefix": "INDB0",
        "domains": ["indusind.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{12,14})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "IDBI Bank",
        "parser_key": "idbi_standard",
        "header_names": [
            r"\bIDBI\s+BANK\b"
        ],
        "ifsc_prefix": "IBKL0",
        "domains": ["idbibank.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Federal Bank",
        "parser_key": "federal_standard",
        "header_names": [
            r"\bFEDERAL\s+BANK\b"
        ],
        "ifsc_prefix": "FDRL0",
        "domains": ["federalbank.co.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "Bandhan Bank",
        "parser_key": "bandhan_standard",
        "header_names": [
            r"\bBANDHAN\s+BANK\b"
        ],
        "ifsc_prefix": "BDBL0",
        "domains": ["bandhanbank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{14})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "AU Small Finance Bank",
        "parser_key": "au_standard",
        "header_names": [
            r"\bAU\s+SMALL\s+FINANCE\s+BANK\b",
            r"\bAU\s+BANK\b"
        ],
        "ifsc_prefix": "AUBL0",
        "domains": ["aubank.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "City Union Bank",
        "parser_key": "cub_standard",
        "header_names": [
            r"\bCITY\s+UNION\s+BANK\b"
        ],
        "ifsc_prefix": "CIUB0",
        "domains": ["cityunionbank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Karnataka Bank",
        "parser_key": "karnataka_standard",
        "header_names": [
            r"\bKARNATAKA\s+BANK\b"
        ],
        "ifsc_prefix": "KARB0",
        "domains": ["karnatakabank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "South Indian Bank",
        "parser_key": "sib_standard",
        "header_names": [
            r"\bSOUTH\s+INDIAN\s+BANK\b"
        ],
        "ifsc_prefix": "SIBL0",
        "domains": ["southindianbank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Tamilnad Mercantile Bank",
        "parser_key": "tmb_standard",
        "header_names": [
            r"\bTAMILNAD\s+MERCANTILE\s+BANK\b"
        ],
        "ifsc_prefix": "TMBL0",
        "domains": ["tmb.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Jammu & Kashmir Bank",
        "parser_key": "jkb_standard",
        "header_names": [
            r"\bJAMMU\s+(&|AND)\s+KASHMIR\s+BANK\b",
            r"\bJ&K\s+BANK\b"
        ],
        "ifsc_prefix": "JAKA0",
        "domains": ["jkbank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "CSB Bank",
        "parser_key": "csb_standard",
        "header_names": [
            r"\bCSB\s+BANK\b",
            r"\bCATHOLIC\s+SYRIAN\s+BANK\b"
        ],
        "ifsc_prefix": "CSBK0",
        "domains": ["csb.co.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Dhanlaxmi Bank",
        "parser_key": "dhanlaxmi_standard",
        "header_names": [
            r"\bDHANLAXMI\s+BANK\b",
            r"\bDHANBANK\b"
        ],
        "ifsc_prefix": "DLXB0",
        "domains": ["dhanbank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{15})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Nainital Bank",
        "parser_key": "nainital_standard",
        "header_names": [
            r"\bNAINITAL\s+BANK\b"
        ],
        "ifsc_prefix": "NTBL0",
        "domains": ["nainitalbank.co.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{16})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Equitas Small Finance Bank",
        "parser_key": "equitas_standard",
        "header_names": [
            r"\bEQUITAS\s+SMALL\s+FINANCE\s+BANK\b",
            r"\bEQUITAS\s+BANK\b"
        ],
        "ifsc_prefix": "ESFB0",
        "domains": ["equitasbank.com"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{11,16})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "HSBC",
        "parser_key": "hsbc_standard",
        "header_names": [
            r"\bTHE\s+HONGKONG\s+AND\s+SHANGHAI\s+BANKING\s+CORPORATION\b",
            r"\bHSBC\s+BANK\b",
            r"\bHSBC\s+INDIA\b"
        ],
        "ifsc_prefix": "HSBC0",
        "domains": ["hsbc.co.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{9,12})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "DBS Bank",
        "parser_key": "dbs_standard",
        "header_names": [
            r"\bDBS\s+BANK\s+INDIA\b",
            r"\bDBS\s+BANK\b",
            r"\bDEVELOPMENT\s+BANK\s+OF\s+SINGAPORE\b"
        ],
        "ifsc_prefix": "DBSS0",
        "domains": ["dbs.com", "dbs.com/in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,13})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Deutsche Bank",
        "parser_key": "deutsche_standard",
        "header_names": [
            r"\bDEUTSCHE\s+BANK\s+AG\b",
            r"\bDEUTSCHE\s+BANK\b"
        ],
        "ifsc_prefix": "DEUT0",
        "domains": ["deutschebank.co.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,12})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Barclays",
        "parser_key": "barclays_standard",
        "header_names": [
            r"\bBARCLAYS\s+BANK\s+PLC\b",
            r"\bBARCLAYS\s+BANK\b"
        ],
        "ifsc_prefix": "BARC0",
        "domains": ["barclays.in"],
        "header_markers": [],
        "account_patterns": [
            r"(?:Account\s+Number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{10,12})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "Kangra Central Co-operative Bank",
        "parser_key": "kccb_standard",
        "header_names": [
            r"\bKANGRA\s+CENTRAL\s+CO-?OP(?:ERATIVE)?\s+BANK\b",
            r"\bKCCB\b",
            r"\bKANGRA\s+CO-?OPERATIVE\b"
        ],
        "ifsc_prefix": "KACE0",
        "domains": ["kccb.in"],
        "header_markers": [
            r"SAVING\s+NON-CHQ",
            r"STATEMENT\s+OF\s+ACCOUNT\s+KANGRA"
        ],
        "account_patterns": [
            r"(?:Account\s+No\.?|A/c\s*No\.?)\s*[:\-]?\s*([0-9]{11})\b"
        ],
        "column_patterns": [],
        "priority": 9
    },
    {
        "bank_name": "The Co-operative Bank",
        "parser_key": "coop_standard",
        "header_names": [
            r"\bTHE\s+CO-?OPERATIVE\s+BANK\b",
            r"\bCO-?OPERATIVE\s+BANK\s+PLC\b"
        ],
        "ifsc_prefix": None,
        "domains": ["co-operativebank.co.uk"],
        "header_markers": [
            r"cashminder\s+statement",
            r"Sort\s+code\s*:"
        ],
        "account_patterns": [
            r"(?:Account\s+number|Account\s+No\.?)\s*[:\-]?\s*([0-9]{8})\b"
        ],
        "column_patterns": [],
        "priority": 8
    },
    {
        "bank_name": "PayPal",
        "parser_key": "paypal_standard",
        "header_names": [
            r"\bPAYPAL\s+SAVINGS\b",
            r"\bPAYPAL\b"
        ],
        "ifsc_prefix": None,
        "domains": ["paypal.com"],
        "header_markers": [
            r"PayPal\s+Savings\s+Statement",
            r"PAYPAL\s+SAVINGS\s+ACCOUNT\s+SUMMARY"
        ],
        "account_patterns": [
            r"(?:Account\s+Number)\s*[:\-]?\s*([0-9]{12})\b"
        ],
        "column_patterns": [],
        "priority": 8
    }
]
