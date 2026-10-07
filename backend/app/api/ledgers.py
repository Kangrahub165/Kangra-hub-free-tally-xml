import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from pydantic import BaseModel
from app.core.security import get_current_user, CurrentUser
from app.accounting.ledger_importer import (
    global_ledger_store,
    import_ledgers_from_text,
    ImportedLedger,
    ImportedGroup,
    LedgerImportResult
)
from app.accounting.tally_master_generator import (
    LedgerDraft,
    generate_ledger_master_xml,
    verify_ledger_round_trip,
    parse_ledger_master_xml
)

router = APIRouter(prefix="/ledgers", tags=["Ledgers"])

def resolve_user_id(request: Request) -> str:
    """Resolves authenticated user ID, or falls back to 'default_session'."""
    auth = request.headers.get("authorization")
    if auth and "bearer " in auth.lower():
        parts = auth.split()
        if len(parts) > 1 and parts[-1].strip():
            return parts[-1][:20]
    return "default_session"

# In-memory bank ledger preferences store: { user_id: { bank_name: bank_ledger_name, "__cash__": cash_ledger } }
USER_BANK_CONFIGS: Dict[str, Dict[str, str]] = {}

class AddLedgerRequest(BaseModel):
    name: str
    group: Optional[str] = "Primary"
    party_gstin: Optional[str] = None
    state: Optional[str] = None

class CreateLedgerMasterRequest(BaseModel):
    name: str
    alias: Optional[str] = None
    parent_group: Optional[str] = "Sundry Creditors"
    address_lines: Optional[List[str]] = []
    state: Optional[str] = "Himachal Pradesh"
    country: Optional[str] = "India"
    pincode: Optional[str] = None
    gstin: Optional[str] = None
    pan: Optional[str] = None
    registration_type: Optional[str] = "Regular"

class BankConfigRequest(BaseModel):
    bank_name: str
    bank_ledger_name: str
    cash_ledger_name: Optional[str] = "Cash"

def decode_ledger_file(contents: bytes) -> str:
    """
    Decodes file bytes safely handling UTF-16LE, UTF-16BE, UTF-8-BOM, UTF-8, UTF-16, and Latin-1.
    Tally exports large master XML files in UTF-16LE with BOM (0xFF 0xFE).
    """
    if contents.startswith(b'\xff\xfe'):
        return contents.decode('utf-16le', errors='replace')
    elif contents.startswith(b'\xfe\xff'):
        return contents.decode('utf-16be', errors='replace')
    elif contents.startswith(b'\xef\xbb\xbf'):
        return contents.decode('utf-8-sig', errors='replace')

    try:
        return contents.decode('utf-8')
    except UnicodeDecodeError:
        pass

    # Check for alternating null bytes typical of UTF-16 without BOM
    if len(contents) > 4 and (contents[1:2] == b'\x00' or contents[0:1] == b'\x00'):
        try:
            return contents.decode('utf-16', errors='replace')
        except UnicodeDecodeError:
            pass

    return contents.decode('latin-1')

@router.post("/import", response_model=LedgerImportResult)
async def import_ledgers_endpoint(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Imports Tally ledgers and groups from XML, JSON, or HTML file.
    Automatically detects format, sanitizes inputs, and indexes ledgers for the authenticated user or session.
    """
    # Max file size 100 MB (supports large Tally master XML exports)
    contents = await file.read()
    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Ledger file exceeds 100 MB limit.")

    try:
        text = decode_ledger_file(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode ledger file text: {str(e)}")

    try:
        result = import_ledgers_from_text(text, filename=file.filename)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ledger import error: {str(e)}")

    # Save to user or session store
    user_id = resolve_user_id(request)
    global_ledger_store.add_ledgers(user_id, result.ledgers)
    if result.groups:
        global_ledger_store.add_groups(user_id, result.groups)

    return result

@router.get("/groups", response_model=List[ImportedGroup])
async def list_user_groups(request: Request):
    """Lists imported groups for the current user or session."""
    user_id = resolve_user_id(request)
    return global_ledger_store.get_user_groups(user_id)

@router.get("/banks", response_model=List[ImportedLedger])
async def list_user_bank_ledgers(request: Request):
    """Lists bank account ledgers from the user's uploaded Tally Master XML."""
    user_id = resolve_user_id(request)
    return global_ledger_store.get_bank_ledgers(user_id)

@router.get("", response_model=List[ImportedLedger])
async def list_user_ledgers(
    request: Request,
    search: Optional[str] = Query(None, description="Search term for ledger name"),
    limit: Optional[int] = Query(None, ge=1, le=50000, description="Max ledgers to return. If omitted, returns all.")
):
    """Lists or searches imported ledgers for the current user or session. Returns all ledgers if limit is omitted."""
    user_id = resolve_user_id(request)
    return global_ledger_store.search_ledgers(user_id, query=search or "", limit=limit)

@router.post("", response_model=ImportedLedger)
async def add_single_ledger_endpoint(
    request: Request,
    req: AddLedgerRequest
):
    """Adds a single ledger directly for the current user or session."""
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Ledger name cannot be empty.")
    user_id = resolve_user_id(request)
    return global_ledger_store.add_single_ledger(
        user_id,
        name=req.name,
        group=req.group,
        party_gstin=req.party_gstin,
        state=req.state
    )

@router.post("/tally-preview")
async def ledger_tally_preview_endpoint(req: CreateLedgerMasterRequest):
    """
    PRD Addendum 6: 'How it will look in Tally' preview for Ledgers.
    Generates XML and parses directly from the XML snippet so the preview reflects what Tally gets.
    """
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Ledger name cannot be empty.")

    try:
        draft = LedgerDraft(
            name=req.name.strip(),
            alias=req.alias,
            parent_group=req.parent_group or "Sundry Creditors",
            address_lines=req.address_lines or [],
            state=req.state or "Himachal Pradesh",
            country=req.country or "India",
            pincode=req.pincode,
            gstin=req.gstin,
            pan=req.pan,
            registration_type=req.registration_type or "Regular"
        )
        xml_str = generate_ledger_master_xml(draft)
        verify_ledger_round_trip(draft, xml_str)
        preview = parse_ledger_master_xml(xml_str)
        return {
            "success": True,
            "preview": preview,
            "xml_snippet": xml_str
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/create-master")
async def create_ledger_master_endpoint(
    request: Request,
    req: CreateLedgerMasterRequest
):
    """
    Creates a new party ledger, verifies round trip, and adds it to the user's ledger store.
    """
    if not req.name or not req.name.strip():
        raise HTTPException(status_code=400, detail="Ledger name cannot be empty.")

    user_id = resolve_user_id(request)
    try:
        draft = LedgerDraft(
            name=req.name.strip(),
            alias=req.alias,
            parent_group=req.parent_group or "Sundry Creditors",
            address_lines=req.address_lines or [],
            state=req.state or "Himachal Pradesh",
            country=req.country or "India",
            pincode=req.pincode,
            gstin=req.gstin,
            pan=req.pan,
            registration_type=req.registration_type or "Regular"
        )
        xml_str = generate_ledger_master_xml(draft)
        verify_ledger_round_trip(draft, xml_str)

        ledger = global_ledger_store.add_single_ledger(
            user_id,
            name=draft.name,
            group=draft.parent_group,
            party_gstin=draft.gstin,
            state=draft.state
        )

        return {
            "success": True,
            "ledger": ledger,
            "xml_snippet": xml_str
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{ledger_name}")
async def delete_ledger_endpoint(
    request: Request,
    ledger_name: str
):
    """Deletes an imported ledger for the current user or session."""
    user_id = resolve_user_id(request)
    success = global_ledger_store.delete_ledger(user_id, ledger_name)
    if not success:
        raise HTTPException(status_code=404, detail="Ledger not found.")
    return {"success": True, "deleted": ledger_name}

@router.get("/config")
async def get_user_bank_configs(request: Request):
    """Returns configured Tally bank and cash ledger names for the user."""
    user_id = resolve_user_id(request)
    configs = USER_BANK_CONFIGS.get(user_id, {
        "State Bank of India": "State Bank of India A/C",
        "Punjab National Bank": "Punjab National Bank A/C",
        "HDFC Bank": "HDFC Bank A/C",
        "ICICI Bank": "ICICI Bank A/C",
        "Axis Bank": "Axis Bank A/C",
        "__cash__": "Cash"
    })
    return configs

@router.post("/config")
async def set_user_bank_config(
    request: Request,
    req: BankConfigRequest
):
    """Saves configured Tally bank and cash ledger names for a specific bank."""
    user_id = resolve_user_id(request)
    if user_id not in USER_BANK_CONFIGS:
        USER_BANK_CONFIGS[user_id] = {"__cash__": "Cash"}
    
    USER_BANK_CONFIGS[user_id][req.bank_name] = req.bank_ledger_name
    if req.cash_ledger_name:
        USER_BANK_CONFIGS[user_id]["__cash__"] = req.cash_ledger_name

    return {
        "success": True,
        "bank_name": req.bank_name,
        "bank_ledger_name": req.bank_ledger_name,
        "cash_ledger_name": USER_BANK_CONFIGS[user_id]["__cash__"]
    }
