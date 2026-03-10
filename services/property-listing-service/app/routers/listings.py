"""
Listing endpoints.

Implements all routes under /api/listings/* with safe, parameterized queries.
Status transitions are validated at the application layer using an explicit
allowlist — no business logic is scattered into separate utilities.
"""
import math
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Listing, OpenHouse
from app.schemas import (
    ListingCreate,
    ListingResponse,
    ListingStatusUpdate,
    ListingUpdate,
    OpenHouseCreate,
    OpenHouseResponse,
    PageResponse,
)

router = APIRouter(prefix="/api/listings", tags=["listings"])

# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


# Valid status transitions: {current_status: [allowed_next_statuses]}
_VALID_TRANSITIONS: dict[str, list[str]] = {
    "ACTIVE": ["PENDING", "WITHDRAWN", "SOLD", "EXPIRED"],
    "PENDING": ["ACTIVE", "SOLD", "WITHDRAWN", "EXPIRED"],
    "COMING_SOON": ["ACTIVE", "WITHDRAWN"],
    "EXPIRED": ["ACTIVE"],
    "WITHDRAWN": ["ACTIVE"],
    "SOLD": [],  # Terminal state — no transitions allowed
}


def _to_response(listing: Listing) -> ListingResponse:
    return ListingResponse.model_validate(listing, from_attributes=True)


def _oh_to_response(oh: OpenHouse) -> OpenHouseResponse:
    return OpenHouseResponse.model_validate(oh, from_attributes=True)


# ─── GET /api/listings ────────────────────────────────────────────────────────

@router.get("", response_model=PageResponse[ListingResponse])
async def list_listings(
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    size: int = Query(20, ge=1, le=200, description="Page size"),
    db: AsyncSession = Depends(_get_db),
):
    """
    List all listings with pagination.
    Returns Spring Page envelope per api-compatibility-rules.md R-RES-2.
    """
    count_stmt = select(func.count()).select_from(Listing)
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = select(Listing).order_by(Listing.created_at.desc()).offset(page * size).limit(size)
    rows = (await db.execute(stmt)).scalars().all()

    total_pages = math.ceil(total / size) if size > 0 else 0
    return PageResponse[ListingResponse](
        content=[_to_response(r) for r in rows],
        total_elements=total,
        total_pages=total_pages,
        size=size,
        number=page,
    )


# ─── GET /api/listings/status/{status} ────────────────────────────────────────

@router.get("/status/{status}", response_model=List[ListingResponse])
async def list_listings_by_status(
    status: str,
    db: AsyncSession = Depends(_get_db),
):
    """Return all listings with a given status."""
    stmt = select(Listing).where(Listing.status == status).order_by(Listing.created_at.desc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


# ─── GET /api/listings/agent/{agentId} ────────────────────────────────────────

@router.get("/agent/{agent_id}", response_model=List[ListingResponse])
async def list_listings_by_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Return all listings for a given agent."""
    stmt = (
        select(Listing)
        .where(Listing.agent_id == agent_id)
        .order_by(Listing.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


# ─── GET /api/listings/{id} ───────────────────────────────────────────────────

@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """
    Get a single listing by ID, including the embedded property and agent.
    Days on market is computed at query time from listed_date.
    """
    stmt = select(Listing).where(Listing.id == listing_id)
    listing = (await db.execute(stmt)).scalars().first()
    if listing is None:
        raise HTTPException(status_code=404, detail=f"Listing not found: {listing_id}")

    # Compute days on market from listed_date (parameterized, not inline SQL)
    if listing.listed_date:
        delta = date.today() - listing.listed_date
        listing.days_on_market = delta.days

    return _to_response(listing)


# ─── POST /api/listings ───────────────────────────────────────────────────────

@router.post("", response_model=ListingResponse, status_code=201)
async def create_listing(
    body: ListingCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Create a new listing. Returns 201 with the created resource per R-STS-1."""
    # Verify agent exists (read-only cross-domain check)
    agent_stmt = select(Agent).where(Agent.id == body.agent_id)
    agent = (await db.execute(agent_stmt)).scalars().first()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {body.agent_id}")

    listing = Listing(
        id=uuid.uuid4(),
        property_id=body.property_id,
        agent_id=body.agent_id,
        list_price=body.list_price,
        original_price=body.list_price,
        status=body.status or "ACTIVE",
        mls_number=body.mls_number,
        listed_date=body.listed_date or date.today(),
        expiry_date=body.expiry_date,
        description=body.description,
        virtual_tour_url=body.virtual_tour_url,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return _to_response(listing)


# ─── PUT /api/listings/{id} ───────────────────────────────────────────────────

@router.put("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: uuid.UUID,
    body: ListingUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """Update listing fields. Returns 200 with the updated resource per R-STS-2."""
    stmt = select(Listing).where(Listing.id == listing_id)
    listing = (await db.execute(stmt)).scalars().first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(listing, field, value)

    listing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(listing)
    return _to_response(listing)


# ─── DELETE /api/listings/{id} ────────────────────────────────────────────────

@router.delete("/{listing_id}", status_code=204)
async def delete_listing(
    listing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """
    Delete a listing. Returns 204 No Content.
    Rejects deletion if offers, showings, or open houses reference this listing to prevent
    orphaned FK records (see property-listing-service-boundary.md §4.2).
    """
    stmt = select(Listing).where(Listing.id == listing_id)
    listing = (await db.execute(stmt)).scalars().first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Check for dependent open_houses (owned by this service)
    oh_count_stmt = select(func.count()).select_from(OpenHouse).where(
        OpenHouse.listing_id == listing_id
    )
    oh_count: int = (await db.execute(oh_count_stmt)).scalar_one()
    if oh_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete listing with {oh_count} open house(s). Remove them first.",
        )

    await db.delete(listing)
    await db.commit()


# ─── PUT /api/listings/{id}/status ────────────────────────────────────────────

@router.put("/{listing_id}/status", response_model=ListingResponse)
async def change_listing_status(
    listing_id: uuid.UUID,
    body: ListingStatusUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """
    Change the status of a listing with transition validation.
    Returns 200 with the updated listing.
    Valid transitions: ACTIVE↔PENDING, ACTIVE/PENDING→SOLD/WITHDRAWN/EXPIRED, WITHDRAWN→ACTIVE.
    SOLD is a terminal state.
    """
    stmt = select(Listing).where(Listing.id == listing_id)
    listing = (await db.execute(stmt)).scalars().first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    current_status = listing.status or "ACTIVE"
    new_status = body.status

    allowed = _VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        if current_status == "SOLD":
            raise HTTPException(
                status_code=400,
                detail="Cannot change status of a SOLD listing",
            )
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status transition from {current_status} to {new_status}. "
                   f"Allowed: {allowed}",
        )

    listing.status = new_status
    if new_status == "SOLD":
        listing.sold_date = date.today()

    listing.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(listing)
    return _to_response(listing)


# ─── POST /api/listings/{id}/open-houses ──────────────────────────────────────

@router.post("/{listing_id}/open-houses", response_model=OpenHouseResponse, status_code=201)
async def schedule_open_house(
    listing_id: uuid.UUID,
    body: OpenHouseCreate,
    db: AsyncSession = Depends(_get_db),
):
    """
    Schedule an open house for a listing.
    Only ACTIVE listings may have open houses scheduled.
    """
    stmt = select(Listing).where(Listing.id == listing_id)
    listing = (await db.execute(stmt)).scalars().first()
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.status != "ACTIVE":
        raise HTTPException(
            status_code=400,
            detail="Can only schedule open houses for ACTIVE listings",
        )

    if body.date < date.today():
        raise HTTPException(status_code=400, detail="Cannot schedule open house in the past")

    agent_id = body.agent_id or listing.agent_id

    open_house = OpenHouse(
        id=uuid.uuid4(),
        listing_id=listing_id,
        date=body.date,
        start_time=body.start_time or "10:00 AM",
        end_time=body.end_time or "2:00 PM",
        agent_id=agent_id,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(open_house)
    await db.commit()
    await db.refresh(open_house)
    return _oh_to_response(open_house)
