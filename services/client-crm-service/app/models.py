"""
SQLAlchemy ORM models for the client-crm-service.

Maps to the existing PostgreSQL schema defined in src/main/resources/schema.sql.
Uses SQLAlchemy 2.0 mapped_column style. No DDL is executed on startup.

Write-owned tables (after Wave 2A cutover):
  clients, client_documents, leads, showings, offers, counter_offers,
  agents, agent_licenses, brokerages, commissions

Read-only cross-domain tables:
  properties, listings, loan_applications
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ─── Read-only cross-domain models ────────────────────────────────────────────

class Property(Base):
    """Read-only. Write ownership belongs to property-listing-service."""
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    property_type: Mapped[Optional[str]] = mapped_column(String(50))


class Listing(Base):
    """Read-only. Write ownership belongs to property-listing-service."""
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id")
    )
    list_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    status: Mapped[Optional[str]] = mapped_column(String(50))
    mls_number: Mapped[Optional[str]] = mapped_column(String(50))
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# ─── Brokerage ────────────────────────────────────────────────────────────────

class Brokerage(Base):
    __tablename__ = "brokerages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    agents: Mapped[List["Agent"]] = relationship(
        "Agent", back_populates="brokerage", lazy="selectin"
    )


# ─── Agent ────────────────────────────────────────────────────────────────────

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    brokerage_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brokerages.id")
    )
    hire_date: Mapped[Optional[date]] = mapped_column(Date)
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    commission_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    # Denormalized columns — not written by this service
    brokerage_name: Mapped[Optional[str]] = mapped_column(String(255))
    brokerage_phone: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    brokerage: Mapped[Optional["Brokerage"]] = relationship(
        "Brokerage", back_populates="agents", lazy="selectin"
    )
    licenses: Mapped[List["AgentLicense"]] = relationship(
        "AgentLicense", back_populates="agent", lazy="selectin"
    )
    commissions: Mapped[List["Commission"]] = relationship(
        "Commission", back_populates="agent", lazy="selectin"
    )


class AgentLicense(Base):
    __tablename__ = "agent_licenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    license_type: Mapped[Optional[str]] = mapped_column(String(100))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    issue_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="ACTIVE")
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="licenses")


class Commission(Base):
    __tablename__ = "commissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id")
    )
    transaction_id: Mapped[Optional[str]] = mapped_column(String(100))
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    commission_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    type: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[str]] = mapped_column(String(50), default="PENDING")
    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    # Denormalized columns — not written by this service
    agent_name: Mapped[Optional[str]] = mapped_column(String(255))
    agent_email: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    agent: Mapped[Optional["Agent"]] = relationship("Agent", back_populates="commissions")


# ─── Client ───────────────────────────────────────────────────────────────────

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    # SSN stored as encrypted — never returned in API responses
    ssn_encrypted: Mapped[Optional[str]] = mapped_column(String(500))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    client_type: Mapped[Optional[str]] = mapped_column(String(50), default="BUYER")
    assigned_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    preferred_contact_method: Mapped[Optional[str]] = mapped_column(String(50))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    # Denormalized columns — not written by this service
    agent_name: Mapped[Optional[str]] = mapped_column(String(255))
    agent_email: Mapped[Optional[str]] = mapped_column(String(255))
    agent_phone: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    assigned_agent: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[assigned_agent_id], lazy="selectin"
    )
    documents: Mapped[List["ClientDocument"]] = relationship(
        "ClientDocument", back_populates="client", lazy="selectin"
    )
    leads: Mapped[List["Lead"]] = relationship(
        "Lead", back_populates="client", lazy="selectin"
    )


class ClientDocument(Base):
    __tablename__ = "client_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False
    )
    document_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_name: Mapped[Optional[str]] = mapped_column(String(500))
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    verified: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="documents")


# ─── Lead ─────────────────────────────────────────────────────────────────────

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id")
    )
    source: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[Optional[str]] = mapped_column(String(50), default="NEW")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    assigned_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    budget_min: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    budget_max: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    property_interest: Mapped[Optional[str]] = mapped_column(Text)
    # Denormalized columns — not written by this service
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    client_email: Mapped[Optional[str]] = mapped_column(String(255))
    client_phone: Mapped[Optional[str]] = mapped_column(String(30))
    agent_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    client: Mapped[Optional["Client"]] = relationship("Client", back_populates="leads")
    assigned_agent: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[assigned_agent_id], lazy="selectin"
    )


# ─── Showing ──────────────────────────────────────────────────────────────────

class Showing(Base):
    __tablename__ = "showings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id")
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id")
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    scheduled_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, default=30)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="SCHEDULED")
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    rating: Mapped[Optional[int]] = mapped_column(Integer)
    # Denormalized columns — not written by this service
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    list_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    client_name: Mapped[Optional[str]] = mapped_column(String(255))
    client_phone: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    listing: Mapped[Optional["Listing"]] = relationship(
        "Listing", foreign_keys=[listing_id], lazy="selectin"
    )
    client: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[client_id], lazy="selectin"
    )
    agent: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[agent_id], lazy="selectin"
    )


# ─── Offer / Counter Offer ────────────────────────────────────────────────────

class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id")
    )
    buyer_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id")
    )
    buyer_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    offer_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    earnest_money: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    contingencies: Mapped[Optional[str]] = mapped_column(Text)
    financing_type: Mapped[Optional[str]] = mapped_column(String(100))
    closing_date_requested: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="SUBMITTED")
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    # Denormalized columns — not written by this service
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    list_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    buyer_name: Mapped[Optional[str]] = mapped_column(String(255))

    listing: Mapped[Optional["Listing"]] = relationship(
        "Listing", foreign_keys=[listing_id], lazy="selectin"
    )
    buyer: Mapped[Optional["Client"]] = relationship(
        "Client", foreign_keys=[buyer_client_id], lazy="selectin"
    )
    buyer_agent: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[buyer_agent_id], lazy="selectin"
    )
    counter_offers: Mapped[List["CounterOffer"]] = relationship(
        "CounterOffer", back_populates="offer", lazy="selectin"
    )


class CounterOffer(Base):
    __tablename__ = "counter_offers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=False
    )
    counter_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    contingencies: Mapped[Optional[str]] = mapped_column(Text)
    closing_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[Optional[str]] = mapped_column(String(50), default="PENDING")
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    offer: Mapped["Offer"] = relationship("Offer", back_populates="counter_offers")
