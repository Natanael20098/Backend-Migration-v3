"""
Brokerage endpoints — /api/brokerages

CRUD for brokerage records. Brokerages are referenced by agents.
Write ownership: client-crm-service (post-Wave 2A cutover).
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import Brokerage
from app.schemas import BrokerageCreate, BrokerageResponse, BrokerageUpdate

router = APIRouter(tags=["brokerages"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(b: Brokerage) -> BrokerageResponse:
    return BrokerageResponse.model_validate(b, from_attributes=True)


async def _require_brokerage(brokerage_id: uuid.UUID, db: AsyncSession) -> Brokerage:
    stmt = select(Brokerage).where(Brokerage.id == brokerage_id)
    brokerage = (await db.execute(stmt)).scalars().first()
    if brokerage is None:
        raise HTTPException(status_code=404, detail=f"Brokerage not found: {brokerage_id}")
    return brokerage


@router.get("/api/brokerages", response_model=List[BrokerageResponse])
async def list_brokerages(
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List all brokerages."""
    stmt = select(Brokerage).order_by(Brokerage.name)
    brokerages = (await db.execute(stmt)).scalars().all()
    return [_to_response(b) for b in brokerages]


@router.get("/api/brokerages/{brokerage_id}", response_model=BrokerageResponse)
async def get_brokerage(
    brokerage_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a brokerage by ID."""
    return _to_response(await _require_brokerage(brokerage_id, db))


@router.post("/api/brokerages", response_model=BrokerageResponse, status_code=201)
async def create_brokerage(
    body: BrokerageCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Create a new brokerage. Returns 201 with created resource."""
    brokerage = Brokerage(
        id=uuid.uuid4(),
        name=body.name,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        city=body.city,
        state=body.state,
        zip_code=body.zip_code,
        phone=body.phone,
        email=body.email,
        license_number=body.license_number,
        website=body.website,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(brokerage)
    await db.commit()
    await db.refresh(brokerage)
    return _to_response(brokerage)


@router.put("/api/brokerages/{brokerage_id}", response_model=BrokerageResponse)
async def update_brokerage(
    brokerage_id: uuid.UUID,
    body: BrokerageUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update a brokerage. Returns 200 with updated resource."""
    brokerage = await _require_brokerage(brokerage_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(brokerage, field, value)
    brokerage.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(brokerage)
    return _to_response(brokerage)


@router.delete("/api/brokerages/{brokerage_id}", status_code=204)
async def delete_brokerage(
    brokerage_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete a brokerage. Returns 204 No Content."""
    brokerage = await _require_brokerage(brokerage_id, db)
    await db.delete(brokerage)
    await db.commit()
