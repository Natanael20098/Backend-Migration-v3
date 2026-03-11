"""
Escrow account and disbursement endpoints.

Implements CRUD routes under:
  /api/closings/{closing_id}/escrow                               — EscrowAccount
  /api/closings/{closing_id}/escrow/{account_id}/disbursements    — EscrowDisbursement

The closing-service owns write access to escrow_accounts and escrow_disbursements
after Wave 3 cutover.
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import ClosingDetail, EscrowAccount, EscrowDisbursement
from app.schemas import (
    EscrowAccountCreate,
    EscrowAccountResponse,
    EscrowAccountUpdate,
    EscrowDisbursementCreate,
    EscrowDisbursementResponse,
    EscrowDisbursementUpdate,
)

router = APIRouter(tags=["escrow"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _account_to_response(account: EscrowAccount) -> EscrowAccountResponse:
    return EscrowAccountResponse.model_validate(account, from_attributes=True)


def _disbursement_to_response(disb: EscrowDisbursement) -> EscrowDisbursementResponse:
    return EscrowDisbursementResponse.model_validate(disb, from_attributes=True)


async def _require_closing(closing_id: uuid.UUID, db: AsyncSession) -> ClosingDetail:
    stmt = select(ClosingDetail).where(ClosingDetail.id == closing_id)
    closing = (await db.execute(stmt)).scalars().first()
    if closing is None:
        raise HTTPException(status_code=404, detail=f"Closing not found: {closing_id}")
    return closing


async def _require_account(
    closing_id: uuid.UUID, account_id: uuid.UUID, db: AsyncSession
) -> EscrowAccount:
    stmt = select(EscrowAccount).where(
        EscrowAccount.id == account_id,
        EscrowAccount.closing_id == closing_id,
    )
    account = (await db.execute(stmt)).scalars().first()
    if account is None:
        raise HTTPException(status_code=404, detail=f"Escrow account not found: {account_id}")
    return account


# ─── GET /api/closings/{closing_id}/escrow ────────────────────────────────────

@router.get(
    "/api/closings/{closing_id}/escrow",
    response_model=List[EscrowAccountResponse],
)
async def list_escrow_accounts(
    closing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List all escrow accounts for a closing."""
    await _require_closing(closing_id, db)
    stmt = (
        select(EscrowAccount)
        .where(EscrowAccount.closing_id == closing_id)
        .order_by(EscrowAccount.created_at.desc())
    )
    accounts = (await db.execute(stmt)).scalars().all()
    return [_account_to_response(a) for a in accounts]


# ─── GET /api/closings/{closing_id}/escrow/{account_id} ──────────────────────

@router.get(
    "/api/closings/{closing_id}/escrow/{account_id}",
    response_model=EscrowAccountResponse,
)
async def get_escrow_account(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a single escrow account with embedded disbursements."""
    await _require_closing(closing_id, db)
    account = await _require_account(closing_id, account_id, db)
    return _account_to_response(account)


# ─── POST /api/closings/{closing_id}/escrow ───────────────────────────────────

@router.post(
    "/api/closings/{closing_id}/escrow",
    response_model=EscrowAccountResponse,
    status_code=201,
)
async def create_escrow_account(
    closing_id: uuid.UUID,
    body: EscrowAccountCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Create an escrow account for a closing. Returns 201 with created resource."""
    await _require_closing(closing_id, db)

    account = EscrowAccount(
        id=uuid.uuid4(),
        closing_id=closing_id,
        account_number=body.account_number,
        balance=body.balance,
        monthly_payment=body.monthly_payment,
        property_tax_reserve=body.property_tax_reserve,
        insurance_reserve=body.insurance_reserve,
        pmi_reserve=body.pmi_reserve,
        cushion_months=body.cushion_months if body.cushion_months is not None else 2,
        status=body.status or "ACTIVE",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return _account_to_response(account)


# ─── PUT /api/closings/{closing_id}/escrow/{account_id} ──────────────────────

@router.put(
    "/api/closings/{closing_id}/escrow/{account_id}",
    response_model=EscrowAccountResponse,
)
async def update_escrow_account(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    body: EscrowAccountUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update an escrow account. Returns 200 with updated resource."""
    await _require_closing(closing_id, db)
    account = await _require_account(closing_id, account_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(account, field, value)
    account.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(account)
    return _account_to_response(account)


# ─── DELETE /api/closings/{closing_id}/escrow/{account_id} ───────────────────

@router.delete(
    "/api/closings/{closing_id}/escrow/{account_id}",
    status_code=204,
)
async def delete_escrow_account(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete an escrow account and all its disbursements. Returns 204 No Content."""
    await _require_closing(closing_id, db)
    account = await _require_account(closing_id, account_id, db)

    # Delete child disbursements first
    disb_stmt = select(EscrowDisbursement).where(
        EscrowDisbursement.escrow_account_id == account_id
    )
    disbursements = (await db.execute(disb_stmt)).scalars().all()
    for disb in disbursements:
        await db.delete(disb)

    await db.delete(account)
    await db.commit()


# ─── GET /api/closings/{closing_id}/escrow/{account_id}/disbursements ─────────

@router.get(
    "/api/closings/{closing_id}/escrow/{account_id}/disbursements",
    response_model=List[EscrowDisbursementResponse],
)
async def list_disbursements(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List all disbursements for an escrow account."""
    await _require_closing(closing_id, db)
    await _require_account(closing_id, account_id, db)

    stmt = (
        select(EscrowDisbursement)
        .where(EscrowDisbursement.escrow_account_id == account_id)
        .order_by(EscrowDisbursement.created_at.desc())
    )
    disbursements = (await db.execute(stmt)).scalars().all()
    return [_disbursement_to_response(d) for d in disbursements]


# ─── GET /api/closings/{closing_id}/escrow/{account_id}/disbursements/{disb_id}

@router.get(
    "/api/closings/{closing_id}/escrow/{account_id}/disbursements/{disb_id}",
    response_model=EscrowDisbursementResponse,
)
async def get_disbursement(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    disb_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a single escrow disbursement by ID."""
    await _require_closing(closing_id, db)
    await _require_account(closing_id, account_id, db)

    stmt = select(EscrowDisbursement).where(
        EscrowDisbursement.id == disb_id,
        EscrowDisbursement.escrow_account_id == account_id,
    )
    disb = (await db.execute(stmt)).scalars().first()
    if disb is None:
        raise HTTPException(status_code=404, detail=f"Escrow disbursement not found: {disb_id}")
    return _disbursement_to_response(disb)


# ─── POST /api/closings/{closing_id}/escrow/{account_id}/disbursements ────────

@router.post(
    "/api/closings/{closing_id}/escrow/{account_id}/disbursements",
    response_model=EscrowDisbursementResponse,
    status_code=201,
)
async def create_disbursement(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    body: EscrowDisbursementCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Record an escrow disbursement. Returns 201 with created resource."""
    await _require_closing(closing_id, db)
    await _require_account(closing_id, account_id, db)

    disb = EscrowDisbursement(
        id=uuid.uuid4(),
        escrow_account_id=account_id,
        disbursement_type=body.disbursement_type,
        amount=body.amount,
        payee=body.payee,
        payee_account=body.payee_account,
        paid_date=body.paid_date,
        period_covered=body.period_covered,
        check_number=body.check_number,
        confirmation=body.confirmation,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(disb)
    await db.commit()
    await db.refresh(disb)
    return _disbursement_to_response(disb)


# ─── PUT /api/closings/{closing_id}/escrow/{account_id}/disbursements/{disb_id}

@router.put(
    "/api/closings/{closing_id}/escrow/{account_id}/disbursements/{disb_id}",
    response_model=EscrowDisbursementResponse,
)
async def update_disbursement(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    disb_id: uuid.UUID,
    body: EscrowDisbursementUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update an escrow disbursement. Returns 200 with updated resource."""
    await _require_closing(closing_id, db)
    await _require_account(closing_id, account_id, db)

    stmt = select(EscrowDisbursement).where(
        EscrowDisbursement.id == disb_id,
        EscrowDisbursement.escrow_account_id == account_id,
    )
    disb = (await db.execute(stmt)).scalars().first()
    if disb is None:
        raise HTTPException(status_code=404, detail=f"Escrow disbursement not found: {disb_id}")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(disb, field, value)

    await db.commit()
    await db.refresh(disb)
    return _disbursement_to_response(disb)


# ─── DELETE /api/closings/{closing_id}/escrow/{account_id}/disbursements/{disb_id}

@router.delete(
    "/api/closings/{closing_id}/escrow/{account_id}/disbursements/{disb_id}",
    status_code=204,
)
async def delete_disbursement(
    closing_id: uuid.UUID,
    account_id: uuid.UUID,
    disb_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete an escrow disbursement. Returns 204 No Content."""
    await _require_closing(closing_id, db)
    await _require_account(closing_id, account_id, db)

    stmt = select(EscrowDisbursement).where(
        EscrowDisbursement.id == disb_id,
        EscrowDisbursement.escrow_account_id == account_id,
    )
    disb = (await db.execute(stmt)).scalars().first()
    if disb is None:
        raise HTTPException(status_code=404, detail=f"Escrow disbursement not found: {disb_id}")

    await db.delete(disb)
    await db.commit()
