"""
Lead endpoints — /api/leads

CRUD for lead records.
Write ownership: client-crm-service (post-Wave 2A cutover).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import Lead
from app.schemas import LeadCreate, LeadResponse, LeadUpdate

router = APIRouter(tags=["leads"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(lead: Lead) -> LeadResponse:
    return LeadResponse.model_validate(lead, from_attributes=True)


async def _require_lead(lead_id: uuid.UUID, db: AsyncSession) -> Lead:
    stmt = select(Lead).where(Lead.id == lead_id)
    lead = (await db.execute(stmt)).scalars().first()
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead not found: {lead_id}")
    return lead


@router.get("/api/leads", response_model=List[LeadResponse])
async def list_leads(
    status: Optional[str] = None,
    assigned_agent_id: Optional[uuid.UUID] = None,
    client_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List leads with optional filters."""
    stmt = select(Lead)
    if status is not None:
        stmt = stmt.where(Lead.status == status)
    if assigned_agent_id is not None:
        stmt = stmt.where(Lead.assigned_agent_id == assigned_agent_id)
    if client_id is not None:
        stmt = stmt.where(Lead.client_id == client_id)
    stmt = stmt.order_by(Lead.created_at.desc())
    leads = (await db.execute(stmt)).scalars().all()
    return [_to_response(l) for l in leads]


@router.get("/api/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a lead by ID."""
    return _to_response(await _require_lead(lead_id, db))


@router.post("/api/leads", response_model=LeadResponse, status_code=201)
async def create_lead(
    body: LeadCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Create a new lead. Returns 201 with created resource."""
    lead = Lead(
        id=uuid.uuid4(),
        client_id=body.client_id,
        source=body.source or "WEBSITE",
        status=body.status or "NEW",
        notes=body.notes,
        assigned_agent_id=body.assigned_agent_id,
        budget_min=body.budget_min,
        budget_max=body.budget_max,
        property_interest=body.property_interest,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return _to_response(lead)


@router.put("/api/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    body: LeadUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update a lead. Returns 200 with updated resource."""
    lead = await _require_lead(lead_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    lead.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(lead)
    return _to_response(lead)


@router.delete("/api/leads/{lead_id}", status_code=204)
async def delete_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete a lead. Returns 204 No Content."""
    lead = await _require_lead(lead_id, db)
    await db.delete(lead)
    await db.commit()
