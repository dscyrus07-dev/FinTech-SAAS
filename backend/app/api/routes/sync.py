"""
Airco Insights — Sync API Route
================================
POST /sync endpoint for receiving spreadsheet updates from frontend.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class SyncRequest(BaseModel):
    """Request model for sync endpoint."""
    sheets: Dict[str, Any]


class SyncResponse(BaseModel):
    """Response model for sync endpoint."""
    status: str
    message: str = "Sync completed successfully"


@router.post("/sync", response_model=SyncResponse)
async def sync_spreadsheet_data(
    request: SyncRequest
):
    """
    Receive spreadsheet updates from frontend and sync with backend.
    
    Args:
        request: SyncRequest containing sheets data
        
    Returns:
        SyncResponse with status
    """
    logger.info("=== SYNC ENDPOINT DEBUG ===")
    logger.info("Received sync request")
    logger.info("Sheets keys: %s", list(request.sheets.keys()))
    
    try:
        # Validate the request structure
        if not request.sheets:
            logger.warning("No sheets data provided")
            raise HTTPException(status_code=400, detail="No sheets data provided")
        
        # Log sheet details for debugging
        for sheet_key, sheet_data in request.sheets.items():
            if isinstance(sheet_data, dict):
                sheet_title = sheet_data.get('title', 'Unknown')
                rows_count = len(sheet_data.get('rows', []))
                headers_count = len(sheet_data.get('headers', []))
                logger.info(f"Sheet: {sheet_title}, Headers: {headers_count}, Rows: {rows_count}")
        
        # TODO: Implement actual sync logic here
        # For now, we just validate and return success
        # In a real implementation, you might:
        # - Save to database
        # - Update cache
        # - Trigger reprocessing
        # - Validate data integrity
        
        logger.info("Sync processing completed successfully")
        logger.info("=== END SYNC ENDPOINT DEBUG ===")
        
        return SyncResponse(status="ok")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Sync processing failed: %s", str(e))
        logger.error("Error details:", exc_info=True)
        logger.info("=== END SYNC ENDPOINT DEBUG ===")
        raise HTTPException(
            status_code=500,
            detail=f"Sync processing failed: {str(e)}"
        )
