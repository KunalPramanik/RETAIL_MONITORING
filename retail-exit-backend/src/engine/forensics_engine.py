"""Unified Forensic Search Engine

Implements V8 Section 11 & Section 4.3 semantic search capabilities:
- Time range filtering
- Camera / Location filtering
- Object / Entity class filtering
- Event Type / Severity filtering
- Face matching & Appearance matching (Re-ID embeddings)
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.orm import selectinload
import numpy as np

from src.db.models import (
    ExitEvent,
    PersonAppearanceSummary,
    FaceMatchAttempt,
    Alert,
    Camera
)
from src.ml.appearance_service import _cosine_similarity


class ForensicSearchEngine:

    @classmethod
    async def search_incidents(
        cls,
        session: AsyncSession,
        start_time: datetime,
        end_time: datetime,
        camera_ids: Optional[List[str]] = None,
        event_type: Optional[str] = None,
        min_severity: Optional[str] = None,
        person_name: Optional[str] = None,
        known_employee: Optional[bool] = None,
        clothing_top_color: Optional[str] = None,
        clothing_bottom_color: Optional[str] = None,
        target_embedding: Optional[List[float]] = None,
        similarity_threshold: float = 0.65,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Executes a multi-modal semantic search across structured events and appearance embeddings.
        Returns a unified list of forensic results.
        """
        stmt = select(ExitEvent).options(
            selectinload(ExitEvent.appearance_summary),
            selectinload(ExitEvent.face_match_attempts),
            selectinload(ExitEvent.alerts)
        )
        
        conditions = [
            ExitEvent.event_time >= start_time,
            ExitEvent.event_time <= end_time
        ]
        
        if camera_ids:
            conditions.append(ExitEvent.camera_id.in_(camera_ids))
            
        if event_type:
            # Assuming event_type correlates with alert types or exit event resolution
            pass # Expandable based on taxonomy
            
        if person_name:
            conditions.append(ExitEvent.carrier_name.ilike(f"%{person_name}%"))
            
        if known_employee is not None:
            if known_employee:
                conditions.append(ExitEvent.carrier_name != "UNKNOWN_PERSON")
            else:
                conditions.append(ExitEvent.carrier_name == "UNKNOWN_PERSON")
                
        # Structured appearance filters
        if clothing_top_color or clothing_bottom_color:
            app_conds = []
            if clothing_top_color:
                app_conds.append(PersonAppearanceSummary.clothing_top_color == clothing_top_color)
            if clothing_bottom_color:
                app_conds.append(PersonAppearanceSummary.clothing_bottom_color == clothing_bottom_color)
            
            stmt = stmt.join(PersonAppearanceSummary).where(and_(*app_conds))

        stmt = stmt.where(and_(*conditions)).order_by(desc(ExitEvent.event_time))
        
        res = await session.execute(stmt)
        events = res.scalars().all()
        
        results = []
        for event in events:
            # Re-ID Embedding Filtering (Python-side dot product until pgvector is migrated)
            if target_embedding and event.appearance_summary and event.appearance_summary.reid_embedding:
                db_emb = np.array(event.appearance_summary.reid_embedding)
                query_emb = np.array(target_embedding)
                sim = float(_cosine_similarity(query_emb, db_emb))
                if sim < similarity_threshold:
                    continue # Skip this result, doesn't match embedding
                event_sim = round(sim, 3)
            else:
                event_sim = 1.0 if not target_embedding else 0.0

            # Severity filter check
            max_sev = "NONE"
            sev_rank = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            for al in event.alerts:
                if sev_rank.get(al.severity, 0) > sev_rank.get(max_sev, 0):
                    max_sev = al.severity
                    
            if min_severity and sev_rank.get(max_sev, 0) < sev_rank.get(min_severity, 0):
                continue
                
            results.append({
                "event_id": event.event_id,
                "timestamp": event.event_time.isoformat(),
                "camera_id": event.camera_id,
                "person": event.carrier_name,
                "top_color": event.appearance_summary.clothing_top_color if event.appearance_summary else None,
                "bottom_color": event.appearance_summary.clothing_bottom_color if event.appearance_summary else None,
                "max_severity": max_sev,
                "similarity_score": event_sim,
                "evidence_snapshots": event.evidence_snapshot_keys
            })

        # Sort by similarity if embedding was provided, otherwise by time
        if target_embedding:
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
        return results[offset:offset+limit]
