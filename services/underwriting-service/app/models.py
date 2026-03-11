"""
SQLAlchemy ORM models for the underwriting-service.

Maps to the existing PostgreSQL schema defined in src/main/resources/schema.sql.
Uses SQLAlchemy 2.0 mapped_column style. No DDL is executed on startup.

Write-owned tables:
  credit_reports, underwriting_decisions, underwriting_conditions,
  appraisal_orders, appraisal_reports, comparable_sales

Read-only cross-domain tables:
  loan_applications, properties, clients, agents
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Read-only cross-domain models ────────────────────────────────────────────

class Agent(Base):
    """Read-only. Write ownership belongs to Java / client-crm-service."""
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Property(Base):
    """Read-only. Write ownership belongs to property-listing-service."""
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    county: Mapped[Optional[str]] = mapped_column(String(100))
    beds: Mapped[Optional[int]] = mapped_column(Integer)
    baths: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))
    sqft: Mapped[Optional[int]] = mapped_column(Integer)
    year_built: Mapped[Optional[int]] = mapped_column(Integer)
    property_type: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Client(Base):
    """Read-only. Write ownership belongs to Java / client-crm-service."""
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class LoanApplication(Base):
    """Read-only. Write ownership belongs to Java / loan-origination-service."""
    __tablename__ = "loan_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    borrower_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id")
    )
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id")
    )
    loan_type: Mapped[Optional[str]] = mapped_column(String(100))
    loan_purpose: Mapped[Optional[str]] = mapped_column(String(100))
    loan_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    interest_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    loan_term_months: Mapped[Optional[int]] = mapped_column(Integer)
    down_payment: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    down_payment_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    application_date: Mapped[Optional[date]] = mapped_column(Date)
    estimated_closing_date: Mapped[Optional[date]] = mapped_column(Date)
    borrower_name: Mapped[Optional[str]] = mapped_column(String(255))
    borrower_email: Mapped[Optional[str]] = mapped_column(String(255))
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    property_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    monthly_payment: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    borrower: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[borrower_id], lazy="selectin"
    )
    property: Mapped[Optional["Property"]] = relationship(
        "Property", foreign_keys=[property_id], lazy="selectin"
    )


# ─── Underwriting-owned models ─────────────────────────────────────────────────

class CreditReport(Base):
    __tablename__ = "credit_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    loan_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_applications.id"), nullable=False
    )
    bureau: Mapped[Optional[str]] = mapped_column(String(50))
    score: Mapped[Optional[int]] = mapped_column(Integer)
    report_date: Mapped[Optional[date]] = mapped_column(Date)
    report_data: Mapped[Optional[str]] = mapped_column(Text)
    pulled_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    # Denormalized columns — not written by this service (legacy only)
    borrower_name: Mapped[Optional[str]] = mapped_column(String(255))
    borrower_ssn_last4: Mapped[Optional[str]] = mapped_column(String(10))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    loan_application: Mapped["LoanApplication"] = relationship(
        "LoanApplication", foreign_keys=[loan_application_id], lazy="selectin"
    )
    pulled_by_agent: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[pulled_by], lazy="selectin"
    )


class UnderwritingDecision(Base):
    __tablename__ = "underwriting_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    loan_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_applications.id"), nullable=False
    )
    underwriter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    decision: Mapped[Optional[str]] = mapped_column(String(50))
    conditions: Mapped[Optional[str]] = mapped_column(Text)
    dti_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    ltv_ratio: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    decision_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Denormalized columns — not written by this service (legacy only)
    loan_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    loan_type: Mapped[Optional[str]] = mapped_column(String(100))
    borrower_name: Mapped[Optional[str]] = mapped_column(String(255))
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    loan_application: Mapped["LoanApplication"] = relationship(
        "LoanApplication", foreign_keys=[loan_application_id], lazy="selectin"
    )
    underwriter: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[underwriter_id], lazy="selectin"
    )
    underwriting_conditions: Mapped[List["UnderwritingCondition"]] = relationship(
        "UnderwritingCondition", back_populates="decision", lazy="selectin"
    )


class UnderwritingCondition(Base):
    __tablename__ = "underwriting_conditions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    decision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("underwriting_decisions.id"), nullable=False
    )
    condition_type: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="PENDING")
    satisfied_date: Mapped[Optional[date]] = mapped_column(Date)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_documents.id")
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    decision: Mapped["UnderwritingDecision"] = relationship(
        "UnderwritingDecision", back_populates="underwriting_conditions"
    )
    assigned_agent: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[assigned_to], lazy="selectin"
    )


class AppraisalOrder(Base):
    __tablename__ = "appraisal_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    loan_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_applications.id"), nullable=False
    )
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id")
    )
    appraiser_name: Mapped[Optional[str]] = mapped_column(String(255))
    appraiser_license: Mapped[Optional[str]] = mapped_column(String(100))
    appraiser_company: Mapped[Optional[str]] = mapped_column(String(255))
    order_date: Mapped[Optional[date]] = mapped_column(Date)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    completed_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="ORDERED")
    fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    rush_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    # Denormalized columns — not written by this service (legacy only)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    property_type: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    loan_application: Mapped["LoanApplication"] = relationship(
        "LoanApplication", foreign_keys=[loan_application_id], lazy="selectin"
    )
    property: Mapped[Optional["Property"]] = relationship(
        "Property", foreign_keys=[property_id], lazy="selectin"
    )
    reports: Mapped[List["AppraisalReport"]] = relationship(
        "AppraisalReport", back_populates="appraisal_order", lazy="selectin"
    )


class AppraisalReport(Base):
    __tablename__ = "appraisal_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appraisal_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_orders.id"), nullable=False
    )
    appraised_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    approach_used: Mapped[Optional[str]] = mapped_column(String(100))
    condition_rating: Mapped[Optional[str]] = mapped_column(String(50))
    quality_rating: Mapped[Optional[str]] = mapped_column(String(50))
    report_date: Mapped[Optional[date]] = mapped_column(Date)
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    report_data: Mapped[Optional[str]] = mapped_column(Text)
    # Denormalized columns — not written by this service (legacy only)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    property_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    property_beds: Mapped[Optional[int]] = mapped_column(Integer)
    property_baths: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    appraisal_order: Mapped["AppraisalOrder"] = relationship(
        "AppraisalOrder", back_populates="reports"
    )
    comparable_sales: Mapped[List["ComparableSale"]] = relationship(
        "ComparableSale", back_populates="appraisal_report", lazy="selectin"
    )


class ComparableSale(Base):
    __tablename__ = "comparable_sales"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    appraisal_report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("appraisal_reports.id"), nullable=False
    )
    address: Mapped[Optional[str]] = mapped_column(String(500))
    sale_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    sale_date: Mapped[Optional[date]] = mapped_column(Date)
    sqft: Mapped[Optional[int]] = mapped_column(Integer)
    beds: Mapped[Optional[int]] = mapped_column(Integer)
    baths: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))
    lot_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    year_built: Mapped[Optional[int]] = mapped_column(Integer)
    distance_miles: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    adjustments: Mapped[Optional[str]] = mapped_column(Text)
    adjusted_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    data_source: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    appraisal_report: Mapped["AppraisalReport"] = relationship(
        "AppraisalReport", back_populates="comparable_sales"
    )
