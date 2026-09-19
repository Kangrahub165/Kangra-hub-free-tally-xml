from fastapi import APIRouter
from typing import List, Dict, Any
from app.parsers.registry import parser_registry

router = APIRouter(prefix="/banks", tags=["Banks"])

@router.get("", response_model=List[Dict[str, Any]])
async def list_supported_banks():
    """Returns dynamic list of all 38+ supported banks and statement formats."""
    return parser_registry.list_all_parsers()
