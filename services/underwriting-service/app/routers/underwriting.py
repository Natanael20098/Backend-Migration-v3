"""
Underwriting decision and condition endpoints.

Implements routes under /api/loans/{loan_id}/underwriting with safe, parameterized queries.
The underwriting-service owns write access to underwriting_decisions and underwriting_conditions
after Wave 3 cutover. loan_applications is read-only.
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoanApplication, UnderwritingCondition, UnderwritingDecision
from app.schemas import (
    UnderwritingConditionCreate,
    UnderwritingConditionResponse,
    UnderwritingConditionUpdate,
    UnderwritingDecisionCreate,
    UnderwritingDecisionResponse,
    UnderwritingDecisionUpdate,
)

router = APIRouter(tags=["underwriting"])


# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _decision_to_response(decision: UnderwritingDecision) -> UnderwritingDecisionResponse:
    return UnderwritingDecisionResponse.model_validate(decision, from_attributes=True)


def _condition_to_response(condition: UnderwritingCondition) -> UnderwritingConditionResponse:
    return UnderwritingConditionResponse.model_validate(condition, from_attributes=True)


async def _require_loan(loan_id: uuid.UUID, db: AsyncSession) -> LoanApplication:
    stmt = select(LoanApplication).where(LoanApplication.id == loan_id)
    loan = (await db.execute(stmt)).scalars().first()
    if loan is None:
        raise HTTPException(status_code=404, detail=f"Loan application not found: {loan_id}")
    return loan


async def _require_decision(
    loan_id: uuid.UUID, decision_id: uuid.UUID, db: AsyncSession
) -> UnderwritingDecision:
    stmt = select(UnderwritingDecision).where(
        UnderwritingDecision.id == decision_id,
        UnderwritingDecision.loan_application_id == loan_id,
    )
    decision = (await db.execute(stmt)).scalars().first()
    if decision is None:
        raise HTTPException(
            status_code=404,
            detail=f"Underwriting decision not found: {decision_id}",
        )
    return decision


# ─── GET /api/loans/{loan_id}/underwriting ───────────────────────────────────

@router.get(
    "/api/loans/{loan_id}/underwriting",
    response_model=List[UnderwritingDecisionResponse],
)
async def list_underwriting_decisions(
    loan_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """List all underwriting decisions for a loan application."""
    await _require_loan(loan_id, db)
    stmt = (
        select(UnderwritingDecision)
        .where(UnderwritingDecision.loan_application_id == loan_id)
        .order_by(UnderwritingDecision.created_at.desc())
    )
    decisions = (await db.execute(stmt)).scalars().all()
    return [_decision_to_response(d) for d in decisions]


# ─── GET /api/loans/{loan_id}/underwriting/{decision_id} ─────────────────────

@router.get(
    "/api/loans/{loan_id}/underwriting/{decision_id}",
    response_model=UnderwritingDecisionResponse,
)
async def get_underwriting_decision(
    loan_id: uuid.UUID,
    decision_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Get a single underwriting decision by ID."""
    await _require_loan(loan_id, db)
    decision = await _require_decision(loan_id, decision_id, db)
    return _decision_to_response(decision)


# ─── POST /api/loans/{loan_id}/underwriting ──────────────────────────────────

@router.post(
    "/api/loans/{loan_id}/underwriting",
    response_model=UnderwritingDecisionResponse,
    status_code=201,
)
async def create_underwriting_decision(
    loan_id: uuid.UUID,
    body: UnderwritingDecisionCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Record an underwriting decision for a loan application. Returns 201."""
    await _require_loan(loan_id, db)

    decision = UnderwritingDecision(
        id=uuid.uuid4(),
        loan_application_id=loan_id,
        underwriter_id=body.underwriter_id,
        decision=body.decision,
        conditions=body.conditions,
        dti_ratio=body.dti_ratio,
        ltv_ratio=body.ltv_ratio,
        risk_score=body.risk_score,
        notes=body.notes,
        decision_date=body.decision_date or datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(decision)
    await db.commit()
    await db.refresh(decision)
    return _decision_to_response(decision)


# ─── PUT /api/loans/{loan_id}/underwriting/{decision_id} ─────────────────────

@router.put(
    "/api/loans/{loan_id}/underwriting/{decision_id}",
    response_model=UnderwritingDecisionResponse,
)
async def update_underwriting_decision(
    loan_id: uuid.UUID,
    decision_id: uuid.UUID,
    body: UnderwritingDecisionUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """Update an existing underwriting decision. Returns 200."""
    await _require_loan(loan_id, db)
    decision = await _require_decision(loan_id, decision_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(decision, field, value)
    decision.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(decision)
    return _decision_to_response(decision)


# ─── DELETE /api/loans/{loan_id}/underwriting/{decision_id} ──────────────────

@router.delete(
    "/api/loans/{loan_id}/underwriting/{decision_id}",
    status_code=204,
)
async def delete_underwriting_decision(
    loan_id: uuid.UUID,
    decision_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Delete an underwriting decision. Returns 204 No Content."""
    await _require_loan(loan_id, db)
    decision = await _require_decision(loan_id, decision_id, db)

    # Delete child conditions first
    cond_stmt = select(UnderwritingCondition).where(
        UnderwritingCondition.decision_id == decision_id
    )
    conditions = (await db.execute(cond_stmt)).scalars().all()
    for cond in conditions:
        await db.delete(cond)

    await db.delete(decision)
    await db.commit()


# ─── GET /api/loans/{loan_id}/underwriting/{decision_id}/conditions ──────────

@router.get(
    "/api/loans/{loan_id}/underwriting/{decision_id}/conditions",
    response_model=List[UnderwritingConditionResponse],
)
async def list_conditions(
    loan_id: uuid.UUID,
    decision_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """List all conditions for an underwriting decision."""
    await _require_loan(loan_id, db)
    await _require_decision(loan_id, decision_id, db)

    stmt = (
        select(UnderwritingCondition)
        .where(UnderwritingCondition.decision_id == decision_id)
        .order_by(UnderwritingCondition.created_at)
    )
    conditions = (await db.execute(stmt)).scalars().all()
    return [_condition_to_response(c) for c in conditions]


# ─── POST /api/loans/{loan_id}/underwriting/{decision_id}/conditions ─────────

@router.post(
    "/api/loans/{loan_id}/underwriting/{decision_id}/conditions",
    response_model=UnderwritingConditionResponse,
    status_code=201,
)
async def create_condition(
    loan_id: uuid.UUID,
    decision_id: uuid.UUID,
    body: UnderwritingConditionCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Add a condition to an underwriting decision. Returns 201."""
    await _require_loan(loan_id, db)
    await _require_decision(loan_id, decision_id, db)

    condition = UnderwritingCondition(
        id=uuid.uuid4(),
        decision_id=decision_id,
        condition_type=body.condition_type,
        description=body.description,
        status=body.status or "PENDING",
        assigned_to=body.assigned_to,
        due_date=body.due_date,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(condition)
    await db.commit()
    await db.refresh(condition)
    return _condition_to_response(condition)


# ─── PUT /api/loans/{loan_id}/underwriting/{decision_id}/conditions/{condition_id} ──

@router.put(
    "/api/loans/{loan_id}/underwriting/{decision_id}/conditions/{condition_id}",
    response_model=UnderwritingConditionResponse,
)
async def update_condition(
    loan_id: uuid.UUID,
    decision_id: uuid.UUID,
    condition_id: uuid.UUID,
    body: UnderwritingConditionUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """Update an underwriting condition. Returns 200."""
    await _require_loan(loan_id, db)
    await _require_decision(loan_id, decision_id, db)

    stmt = select(UnderwritingCondition).where(
        UnderwritingCondition.id == condition_id,
        UnderwritingCondition.decision_id == decision_id,
    )
    condition = (await db.execute(stmt)).scalars().first()
    if condition is None:
        raise HTTPException(
            status_code=404,
            detail=f"Underwriting condition not found: {condition_id}",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(condition, field, value)
    condition.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(condition)
    return _condition_to_response(condition)


# ─── DELETE /api/loans/{loan_id}/underwriting/{decision_id}/conditions/{condition_id} ──

@router.delete(
    "/api/loans/{loan_id}/underwriting/{decision_id}/conditions/{condition_id}",
    status_code=204,
)
async def delete_condition(
    loan_id: uuid.UUID,
    decision_id: uuid.UUID,
    condition_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Delete an underwriting condition. Returns 204."""
    await _require_loan(loan_id, db)
    await _require_decision(loan_id, decision_id, db)

    stmt = select(UnderwritingCondition).where(
        UnderwritingCondition.id == condition_id,
        UnderwritingCondition.decision_id == decision_id,
    )
    condition = (await db.execute(stmt)).scalars().first()
    if condition is None:
        raise HTTPException(
            status_code=404,
            detail=f"Underwriting condition not found: {condition_id}",
        )

    await db.delete(condition)
    await db.commit()
