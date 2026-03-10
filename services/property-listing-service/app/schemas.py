"""
Pydantic schemas for the property-listing-service.

All response models use camelCase aliases (via shared.models.CamelModel) to match the
Java Jackson serialization expected by the frontend (api-compatibility-rules.md R-RES-1).

Request models accept camelCase input fields (with populate_by_name=True allowing snake_case
internal access). UUID fields are serialized as strings per R-RES-7.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import ConfigDict, model_validator
from pydantic.alias_generators import to_camel

from shared.models import CamelModel, PageResponse  # noqa: F401 — re-exported for routers


# ─── Brokerage ────────────────────────────────────────────────────────────────

class BrokerageResponse(CamelModel):
    id: uuid.UUID
    name: Optional[str] = None
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    license_number: Optional[str] = None
    website: Optional[str] = None


# ─── Agent ────────────────────────────────────────────────────────────────────

class AgentResponse(CamelModel):
    id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    is_active: Optional[bool] = None
    commission_rate: Optional[Decimal] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    brokerage: Optional[BrokerageResponse] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ─── Property Image ───────────────────────────────────────────────────────────

class PropertyImageResponse(CamelModel):
    id: uuid.UUID
    property_id: uuid.UUID
    url: Optional[str] = None
    caption: Optional[str] = None
    is_primary: Optional[bool] = None
    display_order: Optional[int] = None
    file_size_bytes: Optional[int] = None
    content_type: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class PropertyImageCreate(CamelModel):
    """Request body for POST /api/properties/{id}/images"""
    url: str
    caption: Optional[str] = None
    is_primary: Optional[bool] = None
    display_order: Optional[int] = None


# ─── Tax Record ───────────────────────────────────────────────────────────────

class TaxRecordResponse(CamelModel):
    id: uuid.UUID
    property_id: uuid.UUID
    year: Optional[int] = None
    assessed_value: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    exemptions: Optional[str] = None
    paid: Optional[bool] = None
    paid_date: Optional[date] = None
    created_at: Optional[datetime] = None


class TaxRecordCreate(CamelModel):
    """Request body for POST /api/properties/{id}/tax-records"""
    year: int
    assessed_value: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    exemptions: Optional[str] = None
    paid: Optional[bool] = None
    paid_date: Optional[date] = None


# ─── Property ─────────────────────────────────────────────────────────────────

class PropertyResponse(CamelModel):
    id: uuid.UUID
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    county: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[Decimal] = None
    sqft: Optional[int] = None
    lot_size: Optional[Decimal] = None
    year_built: Optional[int] = None
    property_type: Optional[str] = None
    description: Optional[str] = None
    parking_spaces: Optional[int] = None
    garage_type: Optional[str] = None
    hoa_fee: Optional[Decimal] = None
    zoning: Optional[str] = None
    parcel_number: Optional[str] = None
    last_sold_price: Optional[Decimal] = None
    last_sold_date: Optional[date] = None
    current_tax_amount: Optional[Decimal] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    images: List[PropertyImageResponse] = []


class PropertyCreate(CamelModel):
    """Request body for POST /api/properties.
    Field names match the Java Property entity field names (camelCase from Jackson)."""
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    zip_code: Optional[str] = None
    county: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[Decimal] = None
    sqft: Optional[int] = None
    lot_size: Optional[Decimal] = None
    year_built: Optional[int] = None
    property_type: Optional[Literal[
        "SINGLE_FAMILY", "CONDO", "TOWNHOUSE", "MULTI_FAMILY", "LAND", "COMMERCIAL"
    ]] = "SINGLE_FAMILY"
    description: Optional[str] = None
    parking_spaces: Optional[int] = None
    garage_type: Optional[str] = None
    hoa_fee: Optional[Decimal] = None
    zoning: Optional[str] = None
    parcel_number: Optional[str] = None


class PropertyUpdate(CamelModel):
    """Request body for PUT /api/properties/{id}. All fields optional."""
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    county: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    beds: Optional[int] = None
    baths: Optional[Decimal] = None
    sqft: Optional[int] = None
    lot_size: Optional[Decimal] = None
    year_built: Optional[int] = None
    property_type: Optional[Literal[
        "SINGLE_FAMILY", "CONDO", "TOWNHOUSE", "MULTI_FAMILY", "LAND", "COMMERCIAL"
    ]] = None
    description: Optional[str] = None
    parking_spaces: Optional[int] = None
    garage_type: Optional[str] = None
    hoa_fee: Optional[Decimal] = None
    zoning: Optional[str] = None
    parcel_number: Optional[str] = None


# ─── Listing ──────────────────────────────────────────────────────────────────

class ListingResponse(CamelModel):
    id: uuid.UUID
    list_price: Optional[Decimal] = None
    original_price: Optional[Decimal] = None
    status: Optional[str] = None
    mls_number: Optional[str] = None
    listed_date: Optional[date] = None
    expiry_date: Optional[date] = None
    sold_date: Optional[date] = None
    sold_price: Optional[Decimal] = None
    days_on_market: Optional[int] = None
    description: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    property: Optional[PropertyResponse] = None
    agent: Optional[AgentResponse] = None


class ListingCreate(CamelModel):
    """Request body for POST /api/listings."""
    property_id: uuid.UUID
    agent_id: uuid.UUID
    list_price: Decimal
    status: Optional[Literal[
        "ACTIVE", "PENDING", "SOLD", "EXPIRED", "WITHDRAWN", "COMING_SOON"
    ]] = "ACTIVE"
    mls_number: Optional[str] = None
    listed_date: Optional[date] = None
    expiry_date: Optional[date] = None
    description: Optional[str] = None
    virtual_tour_url: Optional[str] = None


class ListingUpdate(CamelModel):
    """Request body for PUT /api/listings/{id}. All fields optional."""
    list_price: Optional[Decimal] = None
    status: Optional[Literal[
        "ACTIVE", "PENDING", "SOLD", "EXPIRED", "WITHDRAWN", "COMING_SOON"
    ]] = None
    mls_number: Optional[str] = None
    listed_date: Optional[date] = None
    expiry_date: Optional[date] = None
    sold_date: Optional[date] = None
    sold_price: Optional[Decimal] = None
    description: Optional[str] = None
    virtual_tour_url: Optional[str] = None


class ListingStatusUpdate(CamelModel):
    """Request body for PUT /api/listings/{id}/status."""
    status: Literal["ACTIVE", "PENDING", "SOLD", "WITHDRAWN"]


# ─── Open House ───────────────────────────────────────────────────────────────

class OpenHouseResponse(CamelModel):
    id: uuid.UUID
    listing_id: uuid.UUID
    date: Optional[date] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    agent_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    attendee_count: Optional[int] = None
    created_at: Optional[datetime] = None


class OpenHouseCreate(CamelModel):
    """Request body for POST /api/listings/{id}/open-houses."""
    date: date
    start_time: Optional[str] = "10:00 AM"
    end_time: Optional[str] = "2:00 PM"
    agent_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None
