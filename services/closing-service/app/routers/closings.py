"""
Closing detail endpoints.

Implements CRUD routes under /api/closings with safe, parameterized queries.
The closing-service owns write access to closing_details after Wave 3 cutover.
loan_applications and listings are read-only cross-domain references.
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import ClosingDetail, ClosingDocument, EscrowAccount, EscrowDisbursement, TitleReport
from app.schemas import (
    ClosingDetailCreate,
    ClosingDetailResponse,
    ClosingDetailUpdate,
)

router = APIRouter(tags=["closings"])

# Auth dependency — validates Bearer JWT using shared secret
_get_current_user = make_get_current_user(settings.JWT_SECRET)


# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(closing: ClosingDetail) -> ClosingDetailResponse:
    return ClosingDetailResponse.model_validate(closing, from_attributes=True)


async def _require_closing(closing_id: uuid.UUID, db: AsyncSession) -> ClosingDetail:
    stmt = select(ClosingDetail).where(ClosingDetail.id == closing_id)
    closing = (await db.execute(stmt)).scalars().first()
    if closing is None:
        raise HTTPException(status_code=404, detail=f"Closing not found: {closing_id}")
    return closing


# ─── GET /api/closings ────────────────────────────────────────────────────────

@router.get("/api/closings", response_model=List[ClosingDetailResponse])
async def list_closings(
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List all closing details."""
    stmt = select(ClosingDetail).order_by(ClosingDetail.created_at.desc())
    closings = (await db.execute(stmt)).scalars().all()
    return [_to_response(c) for c in closings]


# ─── GET /api/closings/{closing_id} ──────────────────────────────────────────

@router.get("/api/closings/{closing_id}", response_model=ClosingDetailResponse)
async def get_closing(
    closing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a single closing detail with all sub-resources."""
    closing = await _require_closing(closing_id, db)
    return _to_response(closing)


# ─── POST /api/closings ───────────────────────────────────────────────────────

@router.post("/api/closings", response_model=ClosingDetailResponse, status_code=201)
async def create_closing(
    body: ClosingDetailCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Create a new closing record. Returns 201 with created resource."""
    closing = ClosingDetail(
        id=uuid.uuid4(),
        loan_application_id=body.loan_application_id,
        listing_id=body.listing_id,
        closing_date=body.closing_date,
        closing_time=body.closing_time,
        closing_location=body.closing_location,
        closing_agent_name=body.closing_agent_name,
        closing_agent_email=body.closing_agent_email,
        status=body.status or "SCHEDULED",
        total_closing_costs=body.total_closing_costs,
        seller_credits=body.seller_credits,
        buyer_credits=body.buyer_credits,
        proration_date=body.proration_date,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(closing)
    await db.commit()
    await db.refresh(closing)
    return _to_response(closing)


# ─── PUT /api/closings/{closing_id} ──────────────────────────────────────────

@router.put("/api/closings/{closing_id}", response_model=ClosingDetailResponse)
async def update_closing(
    closing_id: uuid.UUID,
    body: ClosingDetailUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update a closing record. Returns 200 with updated resource."""
    closing = await _require_closing(closing_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(closing, field, value)
    closing.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(closing)
    return _to_response(closing)


# ─── DELETE /api/closings/{closing_id} ───────────────────────────────────────

@router.delete("/api/closings/{closing_id}", status_code=204)
async def delete_closing(
    closing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete a closing and all its sub-resources. Returns 204 No Content."""
    closing = await _require_closing(closing_id, db)

    # Delete escrow disbursements → escrow accounts
    ea_stmt = select(EscrowAccount).where(EscrowAccount.closing_id == closing_id)
    escrow_accounts = (await db.execute(ea_stmt)).scalars().all()
    for account in escrow_accounts:
        disb_stmt = select(EscrowDisbursement).where(
            EscrowDisbursement.escrow_account_id == account.id
        )
        disbursements = (await db.execute(disb_stmt)).scalars().all()
        for disb in disbursements:
            await db.delete(disb)
        await db.delete(account)

    # Delete title reports
    tr_stmt = select(TitleReport).where(TitleReport.closing_id == closing_id)
    title_reports = (await db.execute(tr_stmt)).scalars().all()
    for tr in title_reports:
        await db.delete(tr)

    # Delete closing documents
    doc_stmt = select(ClosingDocument).where(ClosingDocument.closing_id == closing_id)
    documents = (await db.execute(doc_stmt)).scalars().all()
    for doc in documents:
        await db.delete(doc)

    await db.delete(closing)
    await db.commit()
