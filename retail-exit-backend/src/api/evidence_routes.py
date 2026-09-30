"""Evidence Chain-of-Custody API Endpoints"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.session import get_db
from src.db.models import EvidenceArtifact
from src.api.deps_auth import require_roles

router = APIRouter(prefix="/evidence", tags=["V8 Evidence Management"])

class EvidenceResponse(BaseModel):
    artifact_id: str
    event_id: str
    camera_id: Optional[str]
    artifact_type: str
    s3_key: str
    cryptographic_hash: str
    captured_at: str

@router.get("/event/{event_id}", response_model=List[EvidenceResponse])
async def get_evidence_for_event(
    event_id: str,
    session: AsyncSession = Depends(get_db),
    user=Depends(require_roles(["SUPER_ADMIN", "INVESTIGATOR", "SECURITY_SUPERVISOR"]))
):
    """Retrieve all chain-of-custody locked evidence artifacts for an event."""
    res = await session.execute(
        select(EvidenceArtifact).where(EvidenceArtifact.event_id == event_id)
    )
    artifacts = res.scalars().all()
    
    return [
        {
            "artifact_id": a.artifact_id,
            "event_id": a.event_id,
            "camera_id": a.camera_id,
            "artifact_type": a.artifact_type,
            "s3_key": a.s3_key,
            "cryptographic_hash": a.cryptographic_hash,
            "captured_at": a.captured_at.isoformat()
        } for a in artifacts
    ]
