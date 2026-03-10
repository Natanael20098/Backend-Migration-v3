"""
SQLAlchemy ORM models for the property-listing-service.

Maps to the existing PostgreSQL schema defined in src/main/resources/schema.sql.
Uses SQLAlchemy 2.0 mapped_column style. No DDL is executed on startup.
"""
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Integer, Numeric,
    String, Text, BigInteger, Time, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    county: Mapped[Optional[str]] = mapped_column(String(100))
    latitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 7))
    beds: Mapped[Optional[int]] = mapped_column(Integer)
    baths: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))
    sqft: Mapped[Optional[int]] = mapped_column(Integer)
    lot_size: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    year_built: Mapped[Optional[int]] = mapped_column(Integer)
    property_type: Mapped[Optional[str]] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)
    parking_spaces: Mapped[Optional[int]] = mapped_column(Integer)
    garage_type: Mapped[Optional[str]] = mapped_column(String(50))
    hoa_fee: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    zoning: Mapped[Optional[str]] = mapped_column(String(50))
    parcel_number: Mapped[Optional[str]] = mapped_column(String(100))
    last_sold_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    last_sold_date: Mapped[Optional[date]] = mapped_column(Date)
    current_tax_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    images: Mapped[List["PropertyImage"]] = relationship(
        "PropertyImage", back_populates="property", lazy="selectin"
    )
    tax_records: Mapped[List["PropertyTaxRecord"]] = relationship(
        "PropertyTaxRecord", back_populates="property", lazy="selectin"
    )
    listings: Mapped[List["Listing"]] = relationship(
        "Listing", back_populates="property", lazy="noload"
    )


class PropertyImage(Base):
    __tablename__ = "property_images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False
    )
    url: Mapped[Optional[str]] = mapped_column(String(500))
    caption: Mapped[Optional[str]] = mapped_column(String(255))
    is_primary: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    display_order: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    content_type: Mapped[Optional[str]] = mapped_column(String(100))
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    property: Mapped["Property"] = relationship("Property", back_populates="images")


class PropertyTaxRecord(Base):
    __tablename__ = "property_tax_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False
    )
    year: Mapped[Optional[int]] = mapped_column(Integer)
    assessed_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    tax_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    tax_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 4))
    exemptions: Mapped[Optional[str]] = mapped_column(Text)
    paid: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    paid_date: Mapped[Optional[date]] = mapped_column(Date)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    property: Mapped["Property"] = relationship("Property", back_populates="tax_records")


class Agent(Base):
    """Read-only model for agent data. Write ownership belongs to Java/client-crm-service."""
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    brokerage_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brokerages.id")
    )
    is_active: Mapped[Optional[bool]] = mapped_column(Boolean)
    commission_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    brokerage_name: Mapped[Optional[str]] = mapped_column(String(255))
    brokerage_phone: Mapped[Optional[str]] = mapped_column(String(30))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    brokerage: Mapped[Optional["Brokerage"]] = relationship(
        "Brokerage", foreign_keys=[brokerage_id], lazy="selectin"
    )
    listings: Mapped[List["Listing"]] = relationship(
        "Listing", back_populates="agent", lazy="noload"
    )


class Brokerage(Base):
    """Read-only model for brokerage data. Write ownership belongs to Java/client-crm-service."""
    __tablename__ = "brokerages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[Optional[str]] = mapped_column(String(50))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    phone: Mapped[Optional[str]] = mapped_column(String(30))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    license_number: Mapped[Optional[str]] = mapped_column(String(100))
    website: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id"), nullable=False
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id"), nullable=False
    )
    list_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    original_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    status: Mapped[Optional[str]] = mapped_column(String(50), default="ACTIVE")
    mls_number: Mapped[Optional[str]] = mapped_column(String(50))
    listed_date: Mapped[Optional[date]] = mapped_column(Date)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date)
    sold_date: Mapped[Optional[date]] = mapped_column(Date)
    sold_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2))
    days_on_market: Mapped[Optional[int]] = mapped_column(Integer)
    # Denormalized columns — not written by this service (legacy only)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    property_city: Mapped[Optional[str]] = mapped_column(String(100))
    property_state: Mapped[Optional[str]] = mapped_column(String(50))
    property_zip: Mapped[Optional[str]] = mapped_column(String(20))
    property_beds: Mapped[Optional[int]] = mapped_column(Integer)
    property_baths: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1))
    property_sqft: Mapped[Optional[int]] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(Text)
    virtual_tour_url: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    property: Mapped["Property"] = relationship(
        "Property", back_populates="listings", lazy="selectin"
    )
    agent: Mapped["Agent"] = relationship(
        "Agent", back_populates="listings", lazy="selectin"
    )


class OpenHouse(Base):
    __tablename__ = "open_houses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False
    )
    date: Mapped[Optional[date]] = mapped_column(Date)
    start_time: Mapped[Optional[str]] = mapped_column(String(20))
    end_time: Mapped[Optional[str]] = mapped_column(String(20))
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id")
    )
    notes: Mapped[Optional[str]] = mapped_column(Text)
    attendee_count: Mapped[Optional[int]] = mapped_column(Integer)
    property_address: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, server_default=func.now())

    listing: Mapped["Listing"] = relationship("Listing", lazy="selectin")
    agent: Mapped[Optional["Agent"]] = relationship(
        "Agent", foreign_keys=[agent_id], lazy="selectin"
    )
