"""
Showing endpoints — /api/showings

CRUD for showing records.
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
from app.models import Showing
from app.schemas import ShowingCreate, ShowingResponse, ShowingUpdate

router = APIRouter(tags=["showings"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(showing: Showing) -> ShowingResponse:
    return ShowingResponse.model_validate(showing, from_attributes=True)


async def _require_showing(showing_id: uuid.UUID, db: AsyncSession) -> Showing:
    stmt = select(Showing).where(Showing.id == showing_id)
    showing = (await db.execute(stmt)).scalars().first()
    if showing is None:
        raise HTTPException(status_code=404, detail=f"Showing not found: {showing_id}")
    return showing


@router.get("/api/showings", response_model=List[ShowingResponse])
async def list_showings(
    status: Optional[str] = None,
    client_id: Optional[uuid.UUID] = None,
    agent_id: Optional[uuid.UUID] = None,
    listing_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List showings with optional filters."""
    stmt = select(Showing)
    if status is not None:
        stmt = stmt.where(Showing.status == status)
    if client_id is not None:
        stmt = stmt.where(Showing.client_id == client_id)
    if agent_id is not None:
        stmt = stmt.where(Showing.agent_id == agent_id)
    if listing_id is not None:
        stmt = stmt.where(Showing.listing_id == listing_id)
    stmt = stmt.order_by(Showing.scheduled_date.desc())
    showings = (await db.execute(stmt)).scalars().all()
    return [_to_response(s) for s in showings]


@router.get("/api/showings/{showing_id}", response_model=ShowingResponse)
async def get_showing(
    showing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a showing by ID."""
    return _to_response(await _require_showing(showing_id, db))


@router.post("/api/showings", response_model=ShowingResponse, status_code=201)
async def create_showing(
    body: ShowingCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Schedule a new showing. Returns 201 with created resource."""
    showing = Showing(
        id=uuid.uuid4(),
        listing_id=body.listing_id,
        client_id=body.client_id,
        agent_id=body.agent_id,
        scheduled_date=body.scheduled_date,
        duration_minutes=body.duration_minutes or 30,
        status=body.status or "SCHEDULED",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(showing)
    await db.commit()
    await db.refresh(showing)
    return _to_response(showing)


@router.put("/api/showings/{showing_id}", response_model=ShowingResponse)
async def update_showing(
    showing_id: uuid.UUID,
    body: ShowingUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update a showing. Returns 200 with updated resource."""
    showing = await _require_showing(showing_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(showing, field, value)
    showing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(showing)
    return _to_response(showing)


@router.delete("/api/showings/{showing_id}", status_code=204)
async def delete_showing(
    showing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete a showing. Returns 204 No Content."""
    showing = await _require_showing(showing_id, db)
    await db.delete(showing)
    await db.commit()
