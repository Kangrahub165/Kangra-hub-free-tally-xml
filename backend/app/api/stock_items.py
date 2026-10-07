import io
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Request
from pydantic import BaseModel
from decimal import Decimal

from app.core.security import CurrentUser
from app.accounting.ledger_importer import decode_ledger_file
from app.accounting.stock_item_importer import (
    global_stock_item_store,
    import_stock_items_from_text,
    ImportedStockItem,
    StockItemImportResult,
    StockItemMatchSuggestion
)

router = APIRouter(prefix="/stock-items", tags=["Stock Items"])

def resolve_user_id(request: Request) -> str:
    """Resolves authenticated user ID, or falls back to 'default_session'."""
    auth = request.headers.get("authorization")
    if auth and "bearer " in auth.lower():
        # Quick token hash/id
        return auth.split()[-1][:20]
    return "default_session"

class CreateStockItemRequest(BaseModel):
    name: str
    hsn: Optional[str] = None
    uom: Optional[str] = "NOS"
    parent_group: Optional[str] = "Primary"
    gst_rate: Optional[float] = None
    taxability: Optional[str] = "Taxable"
    type_of_supply: Optional[str] = "Goods"
    additional_units: Optional[str] = None
    conversion: Optional[float] = None

class MatchItemsBatchRequest(BaseModel):
    items: List[dict]  # [{"name": "...", "hsn": "..."}]

@router.post("/import", response_model=StockItemImportResult)
async def import_stock_items_endpoint(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Imports Tally stock items from XML (e.g. stock items list sample.xml), JSON, or HTML.
    Supports files up to 100 MB.
    """
    contents = await file.read()
    if len(contents) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Stock item file exceeds 100 MB limit.")

    try:
        text = decode_ledger_file(contents)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to decode stock item file: {str(e)}")

    try:
        result = import_stock_items_from_text(text, filename=file.filename)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stock item import error: {str(e)}")

    user_id = resolve_user_id(request)
    global_stock_item_store.add_items(user_id, result.items)

    return result

@router.get("", response_model=List[ImportedStockItem])
async def list_stock_items_endpoint(
    request: Request,
    search: Optional[str] = Query(None, description="Search item name or HSN"),
    limit: Optional[int] = Query(500, ge=1, le=10000, description="Max items to return")
):
    """Searches and lists imported stock items."""
    user_id = resolve_user_id(request)
    return global_stock_item_store.get_items(user_id, search=search, limit=limit)

@router.post("/match", response_model=List[StockItemMatchSuggestion])
async def match_stock_items_batch(
    request: Request,
    body: MatchItemsBatchRequest
):
    """Batch finds best matching imported stock items for invoice line items."""
    user_id = resolve_user_id(request)
    results = []
    for it in body.items:
        name = it.get("name") or it.get("item_name") or ""
        hsn = it.get("hsn") or it.get("hsn_sac")
        match = global_stock_item_store.match_item(user_id, query_name=name, hsn=hsn)
        results.append(match)
    return results

@router.get("/groups")
async def list_stock_groups_endpoint(request: Request):
    """PRD Addendum 5: Lists distinct Stock Groups from imported Tally items + 'Primary'."""
    user_id = resolve_user_id(request)
    return global_stock_item_store.get_stock_groups(user_id)

@router.get("/units")
async def list_stock_units_endpoint(request: Request):
    """Lists distinct units from imported Tally items."""
    user_id = resolve_user_id(request)
    return global_stock_item_store.get_stock_units(user_id)

@router.post("/create")
async def create_new_stock_item_xml_endpoint(
    request: Request,
    body: CreateStockItemRequest
):
    """
    Creates a new stock item and returns its Tally XML master snippet
    conforming strictly to stock items list sample.xml.
    """
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Stock item name cannot be empty.")

    user_id = resolve_user_id(request)
    gst_dec = Decimal(str(body.gst_rate)) if body.gst_rate is not None else None
    conv_dec = Decimal(str(body.conversion)) if body.conversion is not None else None

    # Save to user's store
    item = ImportedStockItem(
        name=body.name.strip(),
        normalized_name=" ".join(body.name.strip().upper().split()),
        parent=body.parent_group or "Primary",
        base_units=body.uom or "NOS",
        additional_units=body.additional_units,
        hsn_code=body.hsn,
        gst_rate=gst_dec,
        gst_type_of_supply=body.type_of_supply or "Goods",
        source_format="MANUAL"
    )
    global_stock_item_store.add_items(user_id, [item])

    xml_snippet = global_stock_item_store.generate_new_stock_item_xml(
        name=body.name,
        hsn=body.hsn,
        uom=body.uom or "NOS",
        parent_group=body.parent_group or "Primary",
        gst_rate=gst_dec,
        taxability=body.taxability or "Taxable",
        type_of_supply=body.type_of_supply or "Goods",
        additional_units=body.additional_units,
        conversion=conv_dec
    )

    return {
        "success": True,
        "item": item,
        "xml_snippet": xml_snippet
    }

class ExportMasterXmlRequest(BaseModel):
    company_name: Optional[str] = "Kartar Singh & Sons - (from 1-Apr-25)"
    items: List[dict]  # list of item dicts with name, hsn, uom, gst_rate

@router.post("/export-master-xml")
async def export_stock_items_master_xml_endpoint(
    body: ExportMasterXmlRequest
):
    """
    Generates and returns complete Tally All Masters import XML for given items,
    strictly conforming to 'stock items list sample.xml'.
    Includes <UNIT> messages and <STOCKITEM> messages.
    """
    if not body.items:
        raise HTTPException(status_code=400, detail="Items list cannot be empty.")

    xml_content = global_stock_item_store.generate_all_masters_xml(
        company_name=body.company_name or "Kartar Singh & Sons - (from 1-Apr-25)",
        items=body.items
    )

    return {
        "success": True,
        "filename": "Tally_Stock_Items_Master.xml",
        "item_count": len(body.items),
        "xml_content": xml_content
    }
