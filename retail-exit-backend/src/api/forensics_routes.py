"""Forensic Search & Evidence API Endpoints"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from src.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from src.engine.forensics_engine import ForensicSearchEngine
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/forensics", tags=["V8 Unified Forensics"])

class SearchRequest(BaseModel):
    start_time: datetime
    end_time: datetime
    camera_ids: Optional[List[str]] = None
    event_type: Optional[str] = None
    min_severity: Optional[str] = None
    person_name: Optional[str] = None
    known_employee: Optional[bool] = None
    clothing_top_color: Optional[str] = None
    clothing_bottom_color: Optional[str] = None
    target_embedding: Optional[List[float]] = None
    similarity_threshold: float = 0.65
    limit: int = Query(100, le=500)
    offset: int = 0

@router.post("/search")
async def search_incidents(
    req: SearchRequest,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["SUPER_ADMIN", "INVESTIGATOR", "SECURITY_SUPERVISOR"]))
):
    """
    Execute a semantic and structured forensic search across the incident graph.
    """
    try:
        results = await ForensicSearchEngine.search_incidents(
            session=session,
            start_time=req.start_time,
            end_time=req.end_time,
            camera_ids=req.camera_ids,
            event_type=req.event_type,
            min_severity=req.min_severity,
            person_name=req.person_name,
            known_employee=req.known_employee,
            clothing_top_color=req.clothing_top_color,
            clothing_bottom_color=req.clothing_bottom_color,
            target_embedding=req.target_embedding,
            similarity_threshold=req.similarity_threshold,
            limit=req.limit,
            offset=req.offset
        )
        return {"status": "success", "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
