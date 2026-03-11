"""
Pydantic schemas for the closing-service.

All response models use camelCase aliases (via shared.models.CamelModel) to match the
Java Jackson serialization expected by the frontend (api-compatibility-rules.md R-RES-1).

Request models accept camelCase input fields (with populate_by_name=True allowing snake_case
internal access). UUID fields are serialized as strings per R-RES-7.
"""
import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import List, Literal, Optional

from shared.models import CamelModel, PageResponse  # noqa: F401 — re-exported for routers


# ─── Cross-domain read-only response fragments ────────────────────────────────

class ClientSummary(CamelModel):
    id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ListingSummary(CamelModel):
    id: uuid.UUID
    list_price: Optional[Decimal] = None
    status: Optional[str] = None
    mls_number: Optional[str] = None
    property_address: Optional[str] = None
    property_city: Optional[str] = None
    property_state: Optional[str] = None
    property_zip: Optional[str] = None


class LoanApplicationSummary(CamelModel):
    id: uuid.UUID
    loan_type: Optional[str] = None
    loan_purpose: Optional[str] = None
    loan_amount: Optional[Decimal] = None
    status: Optional[str] = None
    application_date: Optional[date] = None
    estimated_closing_date: Optional[date] = None
    actual_closing_date: Optional[date] = None
    borrower: Optional[ClientSummary] = None


# ─── Escrow Disbursement ──────────────────────────────────────────────────────

class EscrowDisbursementResponse(CamelModel):
    id: uuid.UUID
    escrow_account_id: uuid.UUID
    disbursement_type: Optional[str] = None
    amount: Optional[Decimal] = None
    payee: Optional[str] = None
    payee_account: Optional[str] = None
    paid_date: Optional[date] = None
    period_covered: Optional[str] = None
    check_number: Optional[str] = None
    confirmation: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class EscrowDisbursementCreate(CamelModel):
    """Request body for POST /api/closings/{id}/escrow/{accountId}/disbursements"""
    disbursement_type: Literal["PROPERTY_TAX", "HOMEOWNERS_INSURANCE", "PMI", "HOA"]
    amount: Decimal
    payee: str
    payee_account: Optional[str] = None
    paid_date: Optional[date] = None
    period_covered: Optional[str] = None
    check_number: Optional[str] = None
    confirmation: Optional[str] = None
    notes: Optional[str] = None


class EscrowDisbursementUpdate(CamelModel):
    """Request body for PUT /api/closings/{id}/escrow/{accountId}/disbursements/{disbId}"""
    disbursement_type: Optional[Literal["PROPERTY_TAX", "HOMEOWNERS_INSURANCE", "PMI", "HOA"]] = None
    amount: Optional[Decimal] = None
    payee: Optional[str] = None
    payee_account: Optional[str] = None
    paid_date: Optional[date] = None
    period_covered: Optional[str] = None
    check_number: Optional[str] = None
    confirmation: Optional[str] = None
    notes: Optional[str] = None


# ─── Escrow Account ────────────────────────────────────────────────────────────

class EscrowAccountResponse(CamelModel):
    id: uuid.UUID
    closing_id: uuid.UUID
    account_number: Optional[str] = None
    balance: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    property_tax_reserve: Optional[Decimal] = None
    insurance_reserve: Optional[Decimal] = None
    pmi_reserve: Optional[Decimal] = None
    cushion_months: Optional[int] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    disbursements: List[EscrowDisbursementResponse] = []


class EscrowAccountCreate(CamelModel):
    """Request body for POST /api/closings/{id}/escrow"""
    account_number: Optional[str] = None
    balance: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    property_tax_reserve: Optional[Decimal] = None
    insurance_reserve: Optional[Decimal] = None
    pmi_reserve: Optional[Decimal] = None
    cushion_months: Optional[int] = 2
    status: Optional[Literal["ACTIVE", "CLOSED"]] = "ACTIVE"


class EscrowAccountUpdate(CamelModel):
    """Request body for PUT /api/closings/{id}/escrow/{accountId}"""
    account_number: Optional[str] = None
    balance: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    property_tax_reserve: Optional[Decimal] = None
    insurance_reserve: Optional[Decimal] = None
    pmi_reserve: Optional[Decimal] = None
    cushion_months: Optional[int] = None
    status: Optional[Literal["ACTIVE", "CLOSED"]] = None


# ─── Title Report ─────────────────────────────────────────────────────────────

class TitleReportResponse(CamelModel):
    id: uuid.UUID
    closing_id: uuid.UUID
    title_company: Optional[str] = None
    title_number: Optional[str] = None
    status: Optional[str] = None
    issues: Optional[str] = None
    lien_amount: Optional[Decimal] = None
    report_date: Optional[date] = None
    effective_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TitleReportCreate(CamelModel):
    """Request body for POST /api/closings/{id}/title-report"""
    title_company: str
    title_number: Optional[str] = None
    status: Optional[Literal["PENDING", "CLEAR", "LIEN_FOUND", "EXCEPTION"]] = "PENDING"
    issues: Optional[str] = None
    lien_amount: Optional[Decimal] = None
    report_date: Optional[date] = None
    effective_date: Optional[date] = None
    notes: Optional[str] = None


class TitleReportUpdate(CamelModel):
    """Request body for PUT /api/closings/{id}/title-report/{reportId}"""
    title_company: Optional[str] = None
    title_number: Optional[str] = None
    status: Optional[Literal["PENDING", "CLEAR", "LIEN_FOUND", "EXCEPTION"]] = None
    issues: Optional[str] = None
    lien_amount: Optional[Decimal] = None
    report_date: Optional[date] = None
    effective_date: Optional[date] = None
    notes: Optional[str] = None


# ─── Closing Document ─────────────────────────────────────────────────────────

class ClosingDocumentResponse(CamelModel):
    id: uuid.UUID
    closing_id: uuid.UUID
    document_type: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    signed: Optional[bool] = None
    signed_date: Optional[datetime] = None
    signed_by: Optional[str] = None
    notarized: Optional[bool] = None
    notary_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class ClosingDocumentCreate(CamelModel):
    """Request body for POST /api/closings/{id}/documents"""
    document_type: Literal[
        "CLOSING_DISCLOSURE", "DEED", "NOTE", "MORTGAGE", "TITLE_INSURANCE"
    ]
    file_name: str
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    signed: Optional[bool] = False
    signed_date: Optional[datetime] = None
    signed_by: Optional[str] = None
    notarized: Optional[bool] = False
    notary_name: Optional[str] = None
    notes: Optional[str] = None


class ClosingDocumentUpdate(CamelModel):
    """Request body for PUT /api/closings/{id}/documents/{docId}"""
    document_type: Optional[Literal[
        "CLOSING_DISCLOSURE", "DEED", "NOTE", "MORTGAGE", "TITLE_INSURANCE"
    ]] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    signed: Optional[bool] = None
    signed_date: Optional[datetime] = None
    signed_by: Optional[str] = None
    notarized: Optional[bool] = None
    notary_name: Optional[str] = None
    notes: Optional[str] = None


# ─── Closing Detail ───────────────────────────────────────────────────────────

class ClosingDetailResponse(CamelModel):
    id: uuid.UUID
    loan_application_id: Optional[uuid.UUID] = None
    listing_id: Optional[uuid.UUID] = None
    closing_date: Optional[date] = None
    closing_time: Optional[time] = None
    closing_location: Optional[str] = None
    closing_agent_name: Optional[str] = None
    closing_agent_email: Optional[str] = None
    status: Optional[str] = None
    total_closing_costs: Optional[Decimal] = None
    seller_credits: Optional[Decimal] = None
    buyer_credits: Optional[Decimal] = None
    proration_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    loan_application: Optional[LoanApplicationSummary] = None
    listing: Optional[ListingSummary] = None
    documents: List[ClosingDocumentResponse] = []
    title_reports: List[TitleReportResponse] = []
    escrow_accounts: List[EscrowAccountResponse] = []


class ClosingDetailCreate(CamelModel):
    """Request body for POST /api/closings"""
    loan_application_id: Optional[uuid.UUID] = None
    listing_id: Optional[uuid.UUID] = None
    closing_date: Optional[date] = None
    closing_time: Optional[time] = None
    closing_location: Optional[str] = None
    closing_agent_name: Optional[str] = None
    closing_agent_email: Optional[str] = None
    status: Optional[Literal[
        "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "DELAYED"
    ]] = "SCHEDULED"
    total_closing_costs: Optional[Decimal] = None
    seller_credits: Optional[Decimal] = None
    buyer_credits: Optional[Decimal] = None
    proration_date: Optional[date] = None
    notes: Optional[str] = None


class ClosingDetailUpdate(CamelModel):
    """Request body for PUT /api/closings/{id}"""
    loan_application_id: Optional[uuid.UUID] = None
    listing_id: Optional[uuid.UUID] = None
    closing_date: Optional[date] = None
    closing_time: Optional[time] = None
    closing_location: Optional[str] = None
    closing_agent_name: Optional[str] = None
    closing_agent_email: Optional[str] = None
    status: Optional[Literal[
        "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "DELAYED"
    ]] = None
    total_closing_costs: Optional[Decimal] = None
    seller_credits: Optional[Decimal] = None
    buyer_credits: Optional[Decimal] = None
    proration_date: Optional[date] = None
    notes: Optional[str] = None
