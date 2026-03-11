"""
SQLAlchemy ORM models for the closing-service.

Maps to the existing PostgreSQL schema defined in src/main/resources/schema.sql.
Uses SQLAlchemy 2.0 mapped_column style. No DDL is executed on startup.

Write-owned tables:
  closing_details, closing_documents, title_reports,
  escrow_accounts, escrow_disbursements

Read-only cross-domain tables:
  loan_applications, listings, clients
"""
import uuid
from datetime import datetime, date, time
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, Time, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Read-only cross-domain models ────────────────────────────────────────────

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


class Listing(Base):
    """Read-only. Write ownership belongs to property-listing-service."""
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    list_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    mls_number: Mapped[Optional[str]] = mapped_column(String(50))
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    property_city: Mapped[Optional[str]] = mapped_column(String(100))
    property_state: Mapped[Optional[str]] = mapped_column(String(50))
    property_zip: Mapped[Optional[str]] = mapped_column(String(20))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class LoanApplication(Base):
    """Read-only. Write ownership belongs to Java / loan-origination-service."""
    __tablename__ = "loan_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    borrower_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id")
    )
    loan_type: Mapped[Optional[str]] = mapped_column(String(100))
    loan_purpose: Mapped[Optional[str]] = mapped_column(String(100))
    loan_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    application_date: Mapped[Optional[date]] = mapped_column(Date)
    estimated_closing_date: Mapped[Optional[date]] = mapped_column(Date)
    actual_closing_date: Mapped[Optional[date]] = mapped_column(Date)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    borrower: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[borrower_id], lazy="selectin"
    )


# ─── Closing-owned models ──────────────────────────────────────────────────────

class ClosingDetail(Base):
    __tablename__ = "closing_details"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    loan_application_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("loan_applications.id")
    )
    listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id")
    )
    closing_date: Mapped[Optional[date]] = mapped_column(Date)
    closing_time: Mapped[Optional[time]] = mapped_column(Time)
    closing_location: Mapped[Optional[str]] = mapped_column(String(500))
    closing_agent_name: Mapped[Optional[str]] = mapped_column(String(255))
    closing_agent_email: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[str]] = mapped_column(String(50), default="SCHEDULED")
    total_closing_costs: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    seller_credits: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    buyer_credits: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    proration_date: Mapped[Optional[date]] = mapped_column(Date)
    # Denormalized columns — not written by this service (legacy only)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    buyer_name: Mapped[Optional[str]] = mapped_column(String(255))
    seller_name: Mapped[Optional[str]] = mapped_column(String(255))
    loan_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    sale_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    loan_application: Mapped[Optional["LoanApplication"]] = relationship(
        "LoanApplication", foreign_keys=[loan_application_id], lazy="selectin"
    )
    listing: Mapped[Optional["Listing"]] = relationship(
        "Listing", foreign_keys=[listing_id], lazy="selectin"
    )
    documents: Mapped[List["ClosingDocument"]] = relationship(
        "ClosingDocument", back_populates="closing", lazy="selectin"
    )
    title_reports: Mapped[List["TitleReport"]] = relationship(
        "TitleReport", back_populates="closing", lazy="selectin"
    )
    escrow_accounts: Mapped[List["EscrowAccount"]] = relationship(
        "EscrowAccount", back_populates="closing", lazy="selectin"
    )


class ClosingDocument(Base):
    __tablename__ = "closing_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    closing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("closing_details.id"), nullable=False
    )
    document_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_name: Mapped[Optional[str]] = mapped_column(String(500))
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    signed: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    signed_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    signed_by: Mapped[Optional[str]] = mapped_column(String(255))
    notarized: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    notary_name: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    closing: Mapped["ClosingDetail"] = relationship(
        "ClosingDetail", back_populates="documents"
    )


class TitleReport(Base):
    __tablename__ = "title_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    closing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("closing_details.id"), nullable=False
    )
    title_company: Mapped[Optional[str]] = mapped_column(String(255))
    title_number: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[Optional[str]] = mapped_column(String(50), default="PENDING")
    issues: Mapped[Optional[str]] = mapped_column(Text)
    lien_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    report_date: Mapped[Optional[date]] = mapped_column(Date)
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    # Denormalized columns — not written by this service (legacy only)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    owner_name: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    closing: Mapped["ClosingDetail"] = relationship(
        "ClosingDetail", back_populates="title_reports"
    )


class EscrowAccount(Base):
    __tablename__ = "escrow_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    closing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("closing_details.id"), nullable=False
    )
    account_number: Mapped[Optional[str]] = mapped_column(String(100))
    balance: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), default=0)
    monthly_payment: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    property_tax_reserve: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    insurance_reserve: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    pmi_reserve: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    cushion_months: Mapped[Optional[int]] = mapped_column(Integer, default=2)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="ACTIVE")
    # Denormalized columns — not written by this service (legacy only)
    borrower_name: Mapped[Optional[str]] = mapped_column(String(255))
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    closing: Mapped["ClosingDetail"] = relationship(
        "ClosingDetail", back_populates="escrow_accounts"
    )
    disbursements: Mapped[List["EscrowDisbursement"]] = relationship(
        "EscrowDisbursement", back_populates="escrow_account", lazy="selectin"
    )


class EscrowDisbursement(Base):
    __tablename__ = "escrow_disbursements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    escrow_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("escrow_accounts.id"), nullable=False
    )
    disbursement_type: Mapped[Optional[str]] = mapped_column(String(100))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    payee: Mapped[Optional[str]] = mapped_column(String(255))
    payee_account: Mapped[Optional[str]] = mapped_column(String(100))
    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    period_covered: Mapped[Optional[str]] = mapped_column(String(100))
    check_number: Mapped[Optional[str]] = mapped_column(String(50))
    confirmation: Mapped[Optional[str]] = mapped_column(String(100))
    # Denormalized columns — not written by this service (legacy only)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    borrower_name: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    escrow_account: Mapped["EscrowAccount"] = relationship(
        "EscrowAccount", back_populates="disbursements"
    )
