"""
Pydantic schemas for the client-crm-service.

All response models use camelCase aliases (via shared.models.CamelModel) to match the
Java Jackson serialization expected by the frontend (api-compatibility-rules.md R-RES-1).

Request models accept camelCase input fields (populate_by_name=True allowing snake_case access).
UUID fields serialized as strings per R-RES-7.

Security note: ssn_encrypted is NEVER included in any response schema.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from shared.models import CamelModel


# ─── Brokerage schemas ────────────────────────────────────────────────────────

class BrokerageResponse(CamelModel):
    id: uuid.UUID
    name: str
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    license_number: Optional[str] = None
    website: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BrokerageCreate(CamelModel):
    name: str
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    license_number: Optional[str] = None
    website: Optional[str] = None


class BrokerageUpdate(CamelModel):
    name: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    license_number: Optional[str] = None
    website: Optional[str] = None


# ─── Agent License schemas ─────────────────────────────────────────────────────

class AgentLicenseResponse(CamelModel):
    id: uuid.UUID
    agent_id: Optional[uuid.UUID] = None
    license_type: Optional[str] = None
    license_number: Optional[str] = None
    state: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None


class AgentLicenseCreate(CamelModel):
    license_type: str
    license_number: str
    state: str
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[str] = "ACTIVE"


# ─── Commission schemas ────────────────────────────────────────────────────────

class CommissionResponse(CamelModel):
    id: uuid.UUID
    agent_id: Optional[uuid.UUID] = None
    listing_id: Optional[uuid.UUID] = None
    transaction_id: Optional[str] = None
    amount: Optional[Decimal] = None
    commission_rate: Optional[Decimal] = None
    type: Optional[str] = None
    status: Optional[str] = None
    paid_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CommissionCreate(CamelModel):
    listing_id: Optional[uuid.UUID] = None
    transaction_id: Optional[str] = None
    amount: Decimal
    commission_rate: Optional[Decimal] = None
    type: Optional[str] = None
    status: Optional[str] = "PENDING"
    paid_date: Optional[date] = None
    notes: Optional[str] = None


# ─── Agent schemas ────────────────────────────────────────────────────────────

class BrokerageSummary(CamelModel):
    id: uuid.UUID
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class AgentResponse(CamelModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    brokerage_id: Optional[uuid.UUID] = None
    hire_date: Optional[date] = None
    is_active: Optional[bool] = None
    commission_rate: Optional[Decimal] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    brokerage: Optional[BrokerageSummary] = None
    licenses: List[AgentLicenseResponse] = []


class AgentCreate(CamelModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    brokerage_id: Optional[uuid.UUID] = None
    hire_date: Optional[date] = None
    is_active: Optional[bool] = True
    commission_rate: Optional[Decimal] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None


class AgentUpdate(CamelModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    license_number: Optional[str] = None
    brokerage_id: Optional[uuid.UUID] = None
    hire_date: Optional[date] = None
    is_active: Optional[bool] = None
    commission_rate: Optional[Decimal] = None
    bio: Optional[str] = None
    photo_url: Optional[str] = None


# ─── Client Document schemas ──────────────────────────────────────────────────

class ClientDocumentResponse(CamelModel):
    id: uuid.UUID
    client_id: uuid.UUID
    document_type: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    verified: Optional[bool] = None
    verified_by: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    notes: Optional[str] = None
    uploaded_at: Optional[datetime] = None


class ClientDocumentCreate(CamelModel):
    document_type: str
    file_name: str
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: Optional[str] = None
    notes: Optional[str] = None


# ─── Client schemas ───────────────────────────────────────────────────────────

class AgentSummary(CamelModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class ClientResponse(CamelModel):
    """SSN is intentionally excluded from all response models."""
    id: uuid.UUID
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    client_type: Optional[str] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    preferred_contact_method: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    assigned_agent: Optional[AgentSummary] = None
    documents: List[ClientDocumentResponse] = []


class ClientCreate(CamelModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    client_type: Optional[str] = "BUYER"
    assigned_agent_id: Optional[uuid.UUID] = None
    preferred_contact_method: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(CamelModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    client_type: Optional[str] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    preferred_contact_method: Optional[str] = None
    notes: Optional[str] = None


# ─── Lead schemas ─────────────────────────────────────────────────────────────

class LeadResponse(CamelModel):
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    property_interest: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    assigned_agent: Optional[AgentSummary] = None


class LeadCreate(CamelModel):
    client_id: uuid.UUID
    source: Optional[str] = "WEBSITE"
    status: Optional[str] = "NEW"
    notes: Optional[str] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    property_interest: Optional[str] = None


class LeadUpdate(CamelModel):
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    assigned_agent_id: Optional[uuid.UUID] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    property_interest: Optional[str] = None


# ─── Showing schemas ──────────────────────────────────────────────────────────

class ShowingResponse(CamelModel):
    id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    scheduled_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    agent: Optional[AgentSummary] = None


class ShowingCreate(CamelModel):
    listing_id: uuid.UUID
    client_id: uuid.UUID
    agent_id: Optional[uuid.UUID] = None
    scheduled_date: datetime
    duration_minutes: Optional[int] = 30
    status: Optional[str] = "SCHEDULED"
    notes: Optional[str] = None


class ShowingUpdate(CamelModel):
    scheduled_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None
    feedback: Optional[str] = None
    rating: Optional[int] = None


# ─── Counter Offer schemas ────────────────────────────────────────────────────

class CounterOfferResponse(CamelModel):
    id: uuid.UUID
    offer_id: uuid.UUID
    counter_amount: Optional[Decimal] = None
    contingencies: Optional[str] = None
    closing_date: Optional[date] = None
    expiry_date: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class CounterOfferCreate(CamelModel):
    counter_amount: Decimal
    contingencies: Optional[str] = None
    closing_date: Optional[date] = None
    expiry_date: Optional[datetime] = None
    notes: Optional[str] = None


# ─── Offer schemas ────────────────────────────────────────────────────────────

class OfferResponse(CamelModel):
    id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    buyer_client_id: Optional[uuid.UUID] = None
    buyer_agent_id: Optional[uuid.UUID] = None
    offer_amount: Optional[Decimal] = None
    earnest_money: Optional[Decimal] = None
    contingencies: Optional[str] = None
    financing_type: Optional[str] = None
    closing_date_requested: Optional[date] = None
    status: Optional[str] = None
    expiry_date: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    counter_offers: List[CounterOfferResponse] = []


class OfferCreate(CamelModel):
    listing_id: uuid.UUID
    buyer_client_id: uuid.UUID
    buyer_agent_id: Optional[uuid.UUID] = None
    offer_amount: Decimal
    earnest_money: Optional[Decimal] = None
    contingencies: Optional[str] = None
    financing_type: Optional[str] = None
    closing_date_requested: Optional[date] = None
    expiry_date: Optional[datetime] = None


class OfferUpdate(CamelModel):
    offer_amount: Optional[Decimal] = None
    earnest_money: Optional[Decimal] = None
    contingencies: Optional[str] = None
    financing_type: Optional[str] = None
    closing_date_requested: Optional[date] = None
    status: Optional[str] = None
    expiry_date: Optional[datetime] = None
    responded_at: Optional[datetime] = None
