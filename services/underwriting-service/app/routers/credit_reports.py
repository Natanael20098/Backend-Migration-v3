"""
Credit report endpoints.

Implements routes under /api/loans/{loan_id}/credit-report with safe, parameterized queries.
The underwriting-service owns write access to credit_reports after Wave 3 cutover.
loan_applications is read-only (owned by loan-origination-service / Java).
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditReport, LoanApplication
from app.schemas import (
    CreditReportCreate,
    CreditReportResponse,
    CreditReportUpdate,
)

router = APIRouter(tags=["credit-reports"])


# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(report: CreditReport) -> CreditReportResponse:
    return CreditReportResponse.model_validate(report, from_attributes=True)


async def _require_loan(loan_id: uuid.UUID, db: AsyncSession) -> LoanApplication:
    stmt = select(LoanApplication).where(LoanApplication.id == loan_id)
    loan = (await db.execute(stmt)).scalars().first()
    if loan is None:
        raise HTTPException(status_code=404, detail=f"Loan application not found: {loan_id}")
    return loan


# ─── GET /api/loans/{loan_id}/credit-report ───────────────────────────────────

@router.get("/api/loans/{loan_id}/credit-report", response_model=List[CreditReportResponse])
async def list_credit_reports(
    loan_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """List all credit reports for a loan application."""
    await _require_loan(loan_id, db)
    stmt = (
        select(CreditReport)
        .where(CreditReport.loan_application_id == loan_id)
        .order_by(CreditReport.created_at.desc())
    )
    reports = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in reports]


# ─── GET /api/loans/{loan_id}/credit-report/{report_id} ─────────────────────

@router.get(
    "/api/loans/{loan_id}/credit-report/{report_id}",
    response_model=CreditReportResponse,
)
async def get_credit_report(
    loan_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Get a single credit report by ID."""
    await _require_loan(loan_id, db)
    stmt = select(CreditReport).where(
        CreditReport.id == report_id,
        CreditReport.loan_application_id == loan_id,
    )
    report = (await db.execute(stmt)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Credit report not found: {report_id}")
    return _to_response(report)


# ─── POST /api/loans/{loan_id}/credit-report ─────────────────────────────────

@router.post(
    "/api/loans/{loan_id}/credit-report",
    response_model=CreditReportResponse,
    status_code=201,
)
async def create_credit_report(
    loan_id: uuid.UUID,
    body: CreditReportCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Create a credit report for a loan application. Returns 201 with created resource."""
    await _require_loan(loan_id, db)

    report = CreditReport(
        id=uuid.uuid4(),
        loan_application_id=loan_id,
        bureau=body.bureau,
        score=body.score,
        report_date=body.report_date,
        report_data=body.report_data,
        pulled_by=body.pulled_by,
        expiry_date=body.expiry_date,
        created_at=datetime.now(timezone.utc),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return _to_response(report)


# ─── PUT /api/loans/{loan_id}/credit-report/{report_id} ─────────────────────

@router.put(
    "/api/loans/{loan_id}/credit-report/{report_id}",
    response_model=CreditReportResponse,
)
async def update_credit_report(
    loan_id: uuid.UUID,
    report_id: uuid.UUID,
    body: CreditReportUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """Update an existing credit report. Returns 200 with updated resource."""
    await _require_loan(loan_id, db)
    stmt = select(CreditReport).where(
        CreditReport.id == report_id,
        CreditReport.loan_application_id == loan_id,
    )
    report = (await db.execute(stmt)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Credit report not found: {report_id}")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)

    await db.commit()
    await db.refresh(report)
    return _to_response(report)


# ─── DELETE /api/loans/{loan_id}/credit-report/{report_id} ──────────────────

@router.delete(
    "/api/loans/{loan_id}/credit-report/{report_id}",
    status_code=204,
)
async def delete_credit_report(
    loan_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Delete a credit report. Returns 204 No Content."""
    await _require_loan(loan_id, db)
    stmt = select(CreditReport).where(
        CreditReport.id == report_id,
        CreditReport.loan_application_id == loan_id,
    )
    report = (await db.execute(stmt)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Credit report not found: {report_id}")

    await db.delete(report)
    await db.commit()
