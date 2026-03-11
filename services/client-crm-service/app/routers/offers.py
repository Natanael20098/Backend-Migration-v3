"""
Offer endpoints — /api/offers

CRUD for offer records plus counter-offer sub-resource.
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
from app.models import CounterOffer, Offer
from app.schemas import (
    CounterOfferCreate,
    CounterOfferResponse,
    OfferCreate,
    OfferResponse,
    OfferUpdate,
)

router = APIRouter(tags=["offers"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(offer: Offer) -> OfferResponse:
    return OfferResponse.model_validate(offer, from_attributes=True)


async def _require_offer(offer_id: uuid.UUID, db: AsyncSession) -> Offer:
    stmt = select(Offer).where(Offer.id == offer_id)
    offer = (await db.execute(stmt)).scalars().first()
    if offer is None:
        raise HTTPException(status_code=404, detail=f"Offer not found: {offer_id}")
    return offer


@router.get("/api/offers", response_model=List[OfferResponse])
async def list_offers(
    status: Optional[str] = None,
    listing_id: Optional[uuid.UUID] = None,
    buyer_client_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List offers with optional filters."""
    stmt = select(Offer)
    if status is not None:
        stmt = stmt.where(Offer.status == status)
    if listing_id is not None:
        stmt = stmt.where(Offer.listing_id == listing_id)
    if buyer_client_id is not None:
        stmt = stmt.where(Offer.buyer_client_id == buyer_client_id)
    stmt = stmt.order_by(Offer.submitted_at.desc())
    offers = (await db.execute(stmt)).scalars().all()
    return [_to_response(o) for o in offers]


@router.get("/api/offers/{offer_id}", response_model=OfferResponse)
async def get_offer(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get an offer by ID."""
    return _to_response(await _require_offer(offer_id, db))


@router.post("/api/offers", response_model=OfferResponse, status_code=201)
async def create_offer(
    body: OfferCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Submit a new offer. Returns 201 with created resource."""
    offer = Offer(
        id=uuid.uuid4(),
        listing_id=body.listing_id,
        buyer_client_id=body.buyer_client_id,
        buyer_agent_id=body.buyer_agent_id,
        offer_amount=body.offer_amount,
        earnest_money=body.earnest_money,
        contingencies=body.contingencies,
        financing_type=body.financing_type,
        closing_date_requested=body.closing_date_requested,
        status="SUBMITTED",
        expiry_date=body.expiry_date,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(offer)
    await db.commit()
    await db.refresh(offer)
    return _to_response(offer)


@router.put("/api/offers/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: uuid.UUID,
    body: OfferUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update an offer. Returns 200 with updated resource."""
    offer = await _require_offer(offer_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(offer, field, value)
    if body.status in ("ACCEPTED", "REJECTED", "COUNTERED"):
        offer.responded_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(offer)
    return _to_response(offer)


@router.delete("/api/offers/{offer_id}", status_code=204)
async def delete_offer(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete an offer and its counter-offers. Returns 204 No Content."""
    offer = await _require_offer(offer_id, db)
    stmt = select(CounterOffer).where(CounterOffer.offer_id == offer_id)
    counters = (await db.execute(stmt)).scalars().all()
    for c in counters:
        await db.delete(c)
    await db.delete(offer)
    await db.commit()


# ─── Counter Offer sub-resource ───────────────────────────────────────────────

@router.get(
    "/api/offers/{offer_id}/counter-offers",
    response_model=List[CounterOfferResponse],
)
async def list_counter_offers(
    offer_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List counter-offers for an offer."""
    await _require_offer(offer_id, db)
    stmt = select(CounterOffer).where(CounterOffer.offer_id == offer_id)
    counters = (await db.execute(stmt)).scalars().all()
    return [CounterOfferResponse.model_validate(c, from_attributes=True) for c in counters]


@router.post(
    "/api/offers/{offer_id}/counter-offers",
    response_model=CounterOfferResponse,
    status_code=201,
)
async def create_counter_offer(
    offer_id: uuid.UUID,
    body: CounterOfferCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Submit a counter-offer. Returns 201 with created resource."""
    await _require_offer(offer_id, db)
    counter = CounterOffer(
        id=uuid.uuid4(),
        offer_id=offer_id,
        counter_amount=body.counter_amount,
        contingencies=body.contingencies,
        closing_date=body.closing_date,
        expiry_date=body.expiry_date,
        status="PENDING",
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(counter)
    await db.commit()
    await db.refresh(counter)
    return CounterOfferResponse.model_validate(counter, from_attributes=True)
