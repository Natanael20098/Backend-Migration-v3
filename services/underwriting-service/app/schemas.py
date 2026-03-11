"""
Pydantic schemas for the underwriting-service.

All response models use camelCase aliases (via shared.models.CamelModel) to match the
Java Jackson serialization expected by the frontend (api-compatibility-rules.md R-RES-1).

Request models accept camelCase input fields (with populate_by_name=True allowing snake_case
internal access). UUID fields are serialized as strings per R-RES-7.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Literal, Optional

from shared.models import CamelModel, PageResponse  # noqa: F401 — re-exported for routers


# ─── Cross-domain read-only response fragments ────────────────────────────────

class AgentSummary(CamelModel):
    id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class PropertySummary(CamelModel):
    id: uuid.UUID
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[Decimal] = None
    sqft: Optional[int] = None
    property_type: Optional[str] = None


class ClientSummary(CamelModel):
    id: uuid.UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class LoanApplicationSummary(CamelModel):
    id: uuid.UUID
    loan_type: Optional[str] = None
    loan_purpose: Optional[str] = None
    loan_amount: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    loan_term_months: Optional[int] = None
    down_payment: Optional[Decimal] = None
    status: Optional[str] = None
    application_date: Optional[date] = None
    borrower: Optional[ClientSummary] = None
    property: Optional[PropertySummary] = None


# ─── Credit Report ────────────────────────────────────────────────────────────

class CreditReportResponse(CamelModel):
    id: uuid.UUID
    loan_application_id: uuid.UUID
    bureau: Optional[str] = None
    score: Optional[int] = None
    report_date: Optional[date] = None
    report_data: Optional[str] = None
    pulled_by: Optional[uuid.UUID] = None
    expiry_date: Optional[date] = None
    borrower_name: Optional[str] = None
    borrower_ssn_last4: Optional[str] = None
    created_at: Optional[datetime] = None
    loan_application: Optional[LoanApplicationSummary] = None
    pulled_by_agent: Optional[AgentSummary] = None


class CreditReportCreate(CamelModel):
    """Request body for POST /api/loans/{id}/credit-report"""
    bureau: Literal["EQUIFAX", "EXPERIAN", "TRANSUNION"]
    score: int
    report_date: date
    report_data: Optional[str] = None
    pulled_by: Optional[uuid.UUID] = None
    expiry_date: Optional[date] = None


class CreditReportUpdate(CamelModel):
    """Request body for PUT /api/loans/{id}/credit-report/{reportId}"""
    bureau: Optional[Literal["EQUIFAX", "EXPERIAN", "TRANSUNION"]] = None
    score: Optional[int] = None
    report_date: Optional[date] = None
    report_data: Optional[str] = None
    pulled_by: Optional[uuid.UUID] = None
    expiry_date: Optional[date] = None


# ─── Underwriting Condition ───────────────────────────────────────────────────

class UnderwritingConditionResponse(CamelModel):
    id: uuid.UUID
    decision_id: uuid.UUID
    condition_type: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    satisfied_date: Optional[date] = None
    document_id: Optional[uuid.UUID] = None
    assigned_to: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    assigned_agent: Optional[AgentSummary] = None


class UnderwritingConditionCreate(CamelModel):
    """Request body for POST /api/loans/{id}/underwriting/{decisionId}/conditions"""
    condition_type: Literal["PRIOR_TO_DOC", "PRIOR_TO_FUND", "PRIOR_TO_CLOSE"]
    description: str
    status: Optional[Literal["PENDING", "SATISFIED", "WAIVED"]] = "PENDING"
    assigned_to: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


class UnderwritingConditionUpdate(CamelModel):
    """Request body for PUT /api/loans/{id}/underwriting/{decisionId}/conditions/{conditionId}"""
    condition_type: Optional[Literal["PRIOR_TO_DOC", "PRIOR_TO_FUND", "PRIOR_TO_CLOSE"]] = None
    description: Optional[str] = None
    status: Optional[Literal["PENDING", "SATISFIED", "WAIVED"]] = None
    satisfied_date: Optional[date] = None
    document_id: Optional[uuid.UUID] = None
    assigned_to: Optional[uuid.UUID] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None


# ─── Underwriting Decision ────────────────────────────────────────────────────

class UnderwritingDecisionResponse(CamelModel):
    id: uuid.UUID
    loan_application_id: uuid.UUID
    underwriter_id: Optional[uuid.UUID] = None
    decision: Optional[str] = None
    conditions: Optional[str] = None
    dti_ratio: Optional[Decimal] = None
    ltv_ratio: Optional[Decimal] = None
    risk_score: Optional[Decimal] = None
    notes: Optional[str] = None
    decision_date: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    loan_application: Optional[LoanApplicationSummary] = None
    underwriter: Optional[AgentSummary] = None
    underwriting_conditions: List[UnderwritingConditionResponse] = []


class UnderwritingDecisionCreate(CamelModel):
    """Request body for POST /api/loans/{id}/underwriting"""
    underwriter_id: Optional[uuid.UUID] = None
    decision: Literal[
        "APPROVED", "APPROVED_WITH_CONDITIONS", "SUSPENDED", "DENIED"
    ]
    conditions: Optional[str] = None
    dti_ratio: Optional[Decimal] = None
    ltv_ratio: Optional[Decimal] = None
    risk_score: Optional[Decimal] = None
    notes: Optional[str] = None
    decision_date: Optional[datetime] = None


class UnderwritingDecisionUpdate(CamelModel):
    """Request body for PUT /api/loans/{id}/underwriting/{decisionId}"""
    underwriter_id: Optional[uuid.UUID] = None
    decision: Optional[Literal[
        "APPROVED", "APPROVED_WITH_CONDITIONS", "SUSPENDED", "DENIED"
    ]] = None
    conditions: Optional[str] = None
    dti_ratio: Optional[Decimal] = None
    ltv_ratio: Optional[Decimal] = None
    risk_score: Optional[Decimal] = None
    notes: Optional[str] = None
    decision_date: Optional[datetime] = None


# ─── Comparable Sale ──────────────────────────────────────────────────────────

class ComparableSaleResponse(CamelModel):
    id: uuid.UUID
    appraisal_report_id: uuid.UUID
    address: Optional[str] = None
    sale_price: Optional[Decimal] = None
    sale_date: Optional[date] = None
    sqft: Optional[int] = None
    beds: Optional[int] = None
    baths: Optional[Decimal] = None
    lot_size: Optional[Decimal] = None
    year_built: Optional[int] = None
    distance_miles: Optional[Decimal] = None
    adjustments: Optional[str] = None
    adjusted_price: Optional[Decimal] = None
    data_source: Optional[str] = None
    created_at: Optional[datetime] = None


class ComparableSaleCreate(CamelModel):
    """Request body for POST /api/appraisals/{orderId}/reports/{reportId}/comparables"""
    address: str
    sale_price: Decimal
    sale_date: date
    sqft: Optional[int] = None
    beds: Optional[int] = None
    baths: Optional[Decimal] = None
    lot_size: Optional[Decimal] = None
    year_built: Optional[int] = None
    distance_miles: Optional[Decimal] = None
    adjustments: Optional[str] = None
    adjusted_price: Optional[Decimal] = None
    data_source: Optional[str] = None


# ─── Appraisal Report ─────────────────────────────────────────────────────────

class AppraisalReportResponse(CamelModel):
    id: uuid.UUID
    appraisal_order_id: uuid.UUID
    appraised_value: Optional[Decimal] = None
    approach_used: Optional[str] = None
    condition_rating: Optional[str] = None
    quality_rating: Optional[str] = None
    report_date: Optional[date] = None
    effective_date: Optional[date] = None
    report_data: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    comparable_sales: List[ComparableSaleResponse] = []


class AppraisalReportCreate(CamelModel):
    """Request body for POST /api/loans/{id}/appraisal/{orderId}/report"""
    appraised_value: Decimal
    approach_used: Optional[Literal["SALES_COMPARISON", "COST", "INCOME"]] = None
    condition_rating: Optional[str] = None
    quality_rating: Optional[str] = None
    report_date: date
    effective_date: Optional[date] = None
    report_data: Optional[str] = None
    notes: Optional[str] = None


class AppraisalReportUpdate(CamelModel):
    """Request body for PUT /api/loans/{id}/appraisal/{orderId}/report/{reportId}"""
    appraised_value: Optional[Decimal] = None
    approach_used: Optional[Literal["SALES_COMPARISON", "COST", "INCOME"]] = None
    condition_rating: Optional[str] = None
    quality_rating: Optional[str] = None
    report_date: Optional[date] = None
    effective_date: Optional[date] = None
    report_data: Optional[str] = None
    notes: Optional[str] = None


# ─── Appraisal Order ──────────────────────────────────────────────────────────

class AppraisalOrderResponse(CamelModel):
    id: uuid.UUID
    loan_application_id: uuid.UUID
    property_id: Optional[uuid.UUID] = None
    appraiser_name: Optional[str] = None
    appraiser_license: Optional[str] = None
    appraiser_company: Optional[str] = None
    order_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_date: Optional[date] = None
    status: Optional[str] = None
    fee: Optional[Decimal] = None
    rush_fee: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    loan_application: Optional[LoanApplicationSummary] = None
    property: Optional[PropertySummary] = None
    reports: List[AppraisalReportResponse] = []


class AppraisalOrderCreate(CamelModel):
    """Request body for POST /api/loans/{id}/appraisal"""
    property_id: Optional[uuid.UUID] = None
    appraiser_name: Optional[str] = None
    appraiser_license: Optional[str] = None
    appraiser_company: Optional[str] = None
    order_date: Optional[date] = None
    due_date: Optional[date] = None
    status: Optional[Literal[
        "ORDERED", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"
    ]] = "ORDERED"
    fee: Optional[Decimal] = None
    rush_fee: Optional[Decimal] = None
    notes: Optional[str] = None


class AppraisalOrderUpdate(CamelModel):
    """Request body for PUT /api/loans/{id}/appraisal/{orderId}"""
    appraiser_name: Optional[str] = None
    appraiser_license: Optional[str] = None
    appraiser_company: Optional[str] = None
    order_date: Optional[date] = None
    due_date: Optional[date] = None
    completed_date: Optional[date] = None
    status: Optional[Literal[
        "ORDERED", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"
    ]] = None
    fee: Optional[Decimal] = None
    rush_fee: Optional[Decimal] = None
    notes: Optional[str] = None
