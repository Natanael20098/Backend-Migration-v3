"""
Property endpoints.

Implements all routes under /api/properties/* with safe, parameterized queries.
No raw SQL string concatenation — all filtering uses SQLAlchemy Core expressions
or ORM query API per postgresql-access-policy.md and api-compatibility-rules.md.
"""
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property, PropertyImage, PropertyTaxRecord
from app.schemas import (
    PropertyCreate,
    PropertyImageCreate,
    PropertyImageResponse,
    PropertyResponse,
    PropertyUpdate,
    TaxRecordCreate,
    TaxRecordResponse,
    PageResponse,
)

router = APIRouter(prefix="/api/properties", tags=["properties"])

# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _get_db_dep():
    return _get_db


# ─── Helper ───────────────────────────────────────────────────────────────────

def _to_response(prop: Property) -> PropertyResponse:
    return PropertyResponse.model_validate(prop, from_attributes=True)


def _image_to_response(img: PropertyImage) -> PropertyImageResponse:
    return PropertyImageResponse.model_validate(img, from_attributes=True)


def _tax_to_response(rec: PropertyTaxRecord) -> TaxRecordResponse:
    return TaxRecordResponse.model_validate(rec, from_attributes=True)


# ─── GET /api/properties ──────────────────────────────────────────────────────

@router.get("", response_model=PageResponse[PropertyResponse])
async def list_properties(
    page: int = Query(0, ge=0, description="Page number (0-based)"),
    size: int = Query(20, ge=1, le=200, description="Page size"),
    sort: Optional[str] = Query(None, description="Sort field (e.g. city, year_built)"),
    db: AsyncSession = Depends(_get_db),
):
    """
    List all properties with pagination.
    Supports page, size, sort query params per api-compatibility-rules.md R-REQ-4/R-REQ-5.
    Returns Spring Page envelope per R-RES-2.
    """
    # Safe column allowlist for sort to prevent SQL injection
    allowed_sort_columns = {
        "city", "state", "zip_code", "year_built", "sqft",
        "beds", "baths", "created_at", "updated_at",
    }

    count_stmt = select(func.count()).select_from(Property)
    total: int = (await db.execute(count_stmt)).scalar_one()

    stmt = select(Property)
    if sort and sort in allowed_sort_columns:
        stmt = stmt.order_by(getattr(Property, sort))
    else:
        stmt = stmt.order_by(Property.created_at.desc())

    stmt = stmt.offset(page * size).limit(size)
    rows = (await db.execute(stmt)).scalars().all()

    total_pages = math.ceil(total / size) if size > 0 else 0
    return PageResponse[PropertyResponse](
        content=[_to_response(r) for r in rows],
        total_elements=total,
        total_pages=total_pages,
        size=size,
        number=page,
    )


# ─── GET /api/properties/search ───────────────────────────────────────────────

@router.get("/search", response_model=List[PropertyResponse])
async def search_properties(
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None, alias="propertyType"),
    min_bedrooms: Optional[int] = Query(None, alias="minBedrooms"),
    min_price: Optional[Decimal] = Query(None, alias="minPrice"),
    max_price: Optional[Decimal] = Query(None, alias="maxPrice"),
    query: Optional[str] = Query(None, description="Full-text address/city/state search"),
    db: AsyncSession = Depends(_get_db),
):
    """
    Search properties using parameterized WHERE clauses.
    Safe: all filters use SQLAlchemy bound parameters — no string concatenation.
    """
    conditions = []

    if query:
        # Parameterized ILIKE — safe against SQL injection
        pattern = f"%{query}%"
        conditions.append(
            or_(
                Property.address_line1.ilike(pattern),
                Property.city.ilike(pattern),
                Property.state.ilike(pattern),
            )
        )
    if city:
        conditions.append(Property.city.ilike(f"%{city}%"))
    if state:
        conditions.append(Property.state.ilike(f"%{state}%"))
    if property_type:
        conditions.append(Property.property_type == property_type)
    if min_bedrooms is not None:
        conditions.append(Property.beds >= min_bedrooms)

    stmt = select(Property)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(Property.created_at.desc()).limit(200)

    rows = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in rows]


# ─── GET /api/properties/{id} ─────────────────────────────────────────────────

@router.get("/{property_id}", response_model=PropertyResponse)
async def get_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Get a single property by ID, including its images."""
    stmt = select(Property).where(Property.id == property_id)
    prop = (await db.execute(stmt)).scalars().first()
    if prop is None:
        raise HTTPException(status_code=404, detail=f"Property not found: {property_id}")
    return _to_response(prop)


# ─── POST /api/properties ─────────────────────────────────────────────────────

@router.post("", response_model=PropertyResponse, status_code=201)
async def create_property(
    body: PropertyCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Create a new property. Returns 201 with the created resource per R-STS-1."""
    prop = Property(
        id=uuid.uuid4(),
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        city=body.city,
        state=body.state.upper() if body.state else body.state,
        zip_code=body.zip_code,
        county=body.county,
        latitude=body.latitude,
        longitude=body.longitude,
        beds=body.beds,
        baths=body.baths,
        sqft=body.sqft,
        lot_size=body.lot_size,
        year_built=body.year_built,
        property_type=body.property_type or "SINGLE_FAMILY",
        description=body.description,
        parking_spaces=body.parking_spaces,
        garage_type=body.garage_type,
        hoa_fee=body.hoa_fee,
        zoning=body.zoning,
        parcel_number=body.parcel_number,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(prop)
    await db.commit()
    await db.refresh(prop)
    return _to_response(prop)


# ─── PUT /api/properties/{id} ─────────────────────────────────────────────────

@router.put("/{property_id}", response_model=PropertyResponse)
async def update_property(
    property_id: uuid.UUID,
    body: PropertyUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """Update an existing property. Returns 200 with updated resource per R-STS-2."""
    stmt = select(Property).where(Property.id == property_id)
    prop = (await db.execute(stmt)).scalars().first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "state" and value is not None:
            value = value.upper()
        setattr(prop, field, value)

    prop.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(prop)
    return _to_response(prop)


# ─── DELETE /api/properties/{id} ──────────────────────────────────────────────

@router.delete("/{property_id}", status_code=204)
async def delete_property(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """
    Delete a property and cascade to its images and tax records.
    Returns 204 No Content on success.
    """
    stmt = select(Property).where(Property.id == property_id)
    prop = (await db.execute(stmt)).scalars().first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    # Delete child records using parameterized DELETE statements
    await db.execute(
        delete(PropertyImage).where(PropertyImage.property_id == property_id)
    )
    await db.execute(
        delete(PropertyTaxRecord).where(PropertyTaxRecord.property_id == property_id)
    )
    await db.delete(prop)
    await db.commit()


# ─── GET /api/properties/{id}/images ──────────────────────────────────────────

@router.get("/{property_id}/images", response_model=List[PropertyImageResponse])
async def get_images(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Return all images for a property."""
    stmt = select(Property).where(Property.id == property_id)
    prop = (await db.execute(stmt)).scalars().first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    img_stmt = (
        select(PropertyImage)
        .where(PropertyImage.property_id == property_id)
        .order_by(PropertyImage.display_order)
    )
    images = (await db.execute(img_stmt)).scalars().all()
    return [_image_to_response(img) for img in images]


# ─── POST /api/properties/{id}/images ─────────────────────────────────────────

@router.post("/{property_id}/images", response_model=PropertyImageResponse, status_code=201)
async def add_image(
    property_id: uuid.UUID,
    body: PropertyImageCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Add an image to a property. Returns 201 with the created image."""
    stmt = select(Property).where(Property.id == property_id)
    prop = (await db.execute(stmt)).scalars().first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    # Determine display order and primary status using a parameterized count
    count_stmt = select(func.count()).select_from(PropertyImage).where(
        PropertyImage.property_id == property_id
    )
    existing_count: int = (await db.execute(count_stmt)).scalar_one()

    is_primary = body.is_primary if body.is_primary is not None else (existing_count == 0)
    display_order = body.display_order if body.display_order is not None else (existing_count + 1)

    # If setting as primary, unset any existing primary image
    if is_primary:
        prev_primary_stmt = (
            select(PropertyImage)
            .where(
                PropertyImage.property_id == property_id,
                PropertyImage.is_primary == True,  # noqa: E712
            )
        )
        prev_primaries = (await db.execute(prev_primary_stmt)).scalars().all()
        for prev in prev_primaries:
            prev.is_primary = False

    image = PropertyImage(
        id=uuid.uuid4(),
        property_id=property_id,
        url=body.url,
        caption=body.caption,
        is_primary=is_primary,
        display_order=display_order,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return _image_to_response(image)


# ─── GET /api/properties/{id}/tax-records ─────────────────────────────────────

@router.get("/{property_id}/tax-records", response_model=List[TaxRecordResponse])
async def get_tax_records(
    property_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Return all tax records for a property, ordered by year descending."""
    stmt = (
        select(PropertyTaxRecord)
        .where(PropertyTaxRecord.property_id == property_id)
        .order_by(PropertyTaxRecord.year.desc())
    )
    records = (await db.execute(stmt)).scalars().all()
    return [_tax_to_response(r) for r in records]


# ─── POST /api/properties/{id}/tax-records ────────────────────────────────────

@router.post("/{property_id}/tax-records", response_model=TaxRecordResponse, status_code=201)
async def add_tax_record(
    property_id: uuid.UUID,
    body: TaxRecordCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Add a tax record to a property. Returns 409 if a record for that year exists."""
    stmt = select(Property).where(Property.id == property_id)
    prop = (await db.execute(stmt)).scalars().first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    # Check for duplicate year using parameterized query
    dup_stmt = select(PropertyTaxRecord).where(
        PropertyTaxRecord.property_id == property_id,
        PropertyTaxRecord.year == body.year,
    )
    existing = (await db.execute(dup_stmt)).scalars().first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Tax record for year {body.year} already exists",
        )

    record = PropertyTaxRecord(
        id=uuid.uuid4(),
        property_id=property_id,
        year=body.year,
        assessed_value=body.assessed_value,
        tax_amount=body.tax_amount,
        tax_rate=body.tax_rate,
        exemptions=body.exemptions,
        paid=body.paid,
        paid_date=body.paid_date,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    return _tax_to_response(record)
