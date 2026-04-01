"""
Airco Insights — Sync API Route
================================
POST /sync endpoint for receiving spreadsheet updates from frontend.
"""

import logging
import re
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.intelligence import LearningStore

logger = logging.getLogger(__name__)

router = APIRouter()


class SyncRequest(BaseModel):
    """Request model for sync endpoint."""
    sheets: Dict[str, Any]
    learning_events: List[Dict[str, Any]] = Field(default_factory=list)


class LearningEvent(BaseModel):
    sheet_title: Optional[str] = None
    row_index: Optional[int] = None
    description: str
    category: str
    confidence: float = 1.0
    source: str = "user"
    bank_name: str = ""
    account_type: str = ""
    recurring_type: str = ""
    pattern: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SyncResponse(BaseModel):
    """Response model for sync endpoint."""
    status: str
    message: str = "Sync completed successfully"
    learned_events: int = 0
    promoted_rules: List[Dict[str, Any]] = Field(default_factory=list)


def _norm_text(value: Any) -> str:
    text = str(value or "").upper()
    text = re.sub(r"[^A-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_pattern(description: str) -> str:
    tokens = [tok for tok in _norm_text(description).split() if len(tok) > 3]
    if not tokens:
        return ""
    # Prefer stable merchant/employer-like suffixes.
    return tokens[-1]


def _promotion_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "entity": item.get("entity", ""),
        "normalized_entity": item.get("normalized_entity", ""),
        "category": item.get("category", ""),
        "hit_count": item.get("hit_count", 0),
        "confidence": item.get("confidence", 0),
        "bank_name": item.get("bank_name", ""),
        "account_type": item.get("account_type", ""),
    }


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
    
    learning_store = LearningStore()

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

        learned_events = 0
        promoted_rules: List[Dict[str, Any]] = []

        for raw_event in request.learning_events:
            try:
                event = LearningEvent(**raw_event)
            except Exception as exc:
                logger.warning("Skipping malformed learning event: %s", exc)
                continue

            pattern = event.pattern.strip() or _extract_pattern(event.description)
            learning_store.record_observation(
                description=event.description,
                category=event.category,
                confidence=float(event.confidence or 1.0),
                source=event.source,
                bank_name=event.bank_name,
                account_type=event.account_type,
                pattern=pattern,
                recurring_type=event.recurring_type,
                metadata={
                    **event.metadata,
                    "sheet_title": event.sheet_title,
                    "row_index": event.row_index,
                },
            )
            learned_events += 1

        # Promote stable patterns into response hints so the UI/backend can surface them.
        for item in learning_store.export_snapshot():
            if int(item.get("hit_count", 0) or 0) >= 5 and float(item.get("confidence", 0) or 0) >= 0.9:
                promoted_rules.append(_promotion_candidate(item))

        # De-duplicate promotion hints by normalized entity/category.
        deduped: Dict[str, Dict[str, Any]] = {}
        for item in promoted_rules:
            key = f"{item.get('normalized_entity','')}|{item.get('category','')}|{item.get('bank_name','')}"
            deduped[key] = item
        promoted_rules = list(deduped.values())
        
        # TODO: Implement actual sync logic here
        # For now, we just validate and return success
        # In a real implementation, you might:
        # - Save to database
        # - Update cache
        # - Trigger reprocessing
        # - Validate data integrity
        
        logger.info("Sync processing completed successfully")
        logger.info("=== END SYNC ENDPOINT DEBUG ===")
        
        return SyncResponse(status="ok", learned_events=learned_events, promoted_rules=promoted_rules)
        
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
