"""
Appraisal order and report endpoints.

Implements routes under /api/loans/{loan_id}/appraisal with safe, parameterized queries.
The underwriting-service owns write access to appraisal_orders, appraisal_reports, and
comparable_sales after Wave 3 cutover. loan_applications and properties are read-only.
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppraisalOrder, AppraisalReport, ComparableSale, LoanApplication
from app.schemas import (
    AppraisalOrderCreate,
    AppraisalOrderResponse,
    AppraisalOrderUpdate,
    AppraisalReportCreate,
    AppraisalReportResponse,
    AppraisalReportUpdate,
    ComparableSaleCreate,
    ComparableSaleResponse,
)

router = APIRouter(tags=["appraisals"])


# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _order_to_response(order: AppraisalOrder) -> AppraisalOrderResponse:
    return AppraisalOrderResponse.model_validate(order, from_attributes=True)


def _report_to_response(report: AppraisalReport) -> AppraisalReportResponse:
    return AppraisalReportResponse.model_validate(report, from_attributes=True)


def _comp_to_response(comp: ComparableSale) -> ComparableSaleResponse:
    return ComparableSaleResponse.model_validate(comp, from_attributes=True)


async def _require_loan(loan_id: uuid.UUID, db: AsyncSession) -> LoanApplication:
    stmt = select(LoanApplication).where(LoanApplication.id == loan_id)
    loan = (await db.execute(stmt)).scalars().first()
    if loan is None:
        raise HTTPException(status_code=404, detail=f"Loan application not found: {loan_id}")
    return loan


async def _require_order(
    loan_id: uuid.UUID, order_id: uuid.UUID, db: AsyncSession
) -> AppraisalOrder:
    stmt = select(AppraisalOrder).where(
        AppraisalOrder.id == order_id,
        AppraisalOrder.loan_application_id == loan_id,
    )
    order = (await db.execute(stmt)).scalars().first()
    if order is None:
        raise HTTPException(status_code=404, detail=f"Appraisal order not found: {order_id}")
    return order


async def _require_report(
    order_id: uuid.UUID, report_id: uuid.UUID, db: AsyncSession
) -> AppraisalReport:
    stmt = select(AppraisalReport).where(
        AppraisalReport.id == report_id,
        AppraisalReport.appraisal_order_id == order_id,
    )
    report = (await db.execute(stmt)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Appraisal report not found: {report_id}")
    return report


# ─── GET /api/loans/{loan_id}/appraisal ──────────────────────────────────────

@router.get(
    "/api/loans/{loan_id}/appraisal",
    response_model=List[AppraisalOrderResponse],
)
async def list_appraisal_orders(
    loan_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """List all appraisal orders for a loan application."""
    await _require_loan(loan_id, db)
    stmt = (
        select(AppraisalOrder)
        .where(AppraisalOrder.loan_application_id == loan_id)
        .order_by(AppraisalOrder.created_at.desc())
    )
    orders = (await db.execute(stmt)).scalars().all()
    return [_order_to_response(o) for o in orders]


# ─── GET /api/loans/{loan_id}/appraisal/{order_id} ───────────────────────────

@router.get(
    "/api/loans/{loan_id}/appraisal/{order_id}",
    response_model=AppraisalOrderResponse,
)
async def get_appraisal_order(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Get a single appraisal order by ID."""
    await _require_loan(loan_id, db)
    order = await _require_order(loan_id, order_id, db)
    return _order_to_response(order)


# ─── POST /api/loans/{loan_id}/appraisal ─────────────────────────────────────

@router.post(
    "/api/loans/{loan_id}/appraisal",
    response_model=AppraisalOrderResponse,
    status_code=201,
)
async def create_appraisal_order(
    loan_id: uuid.UUID,
    body: AppraisalOrderCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Create an appraisal order for a loan application. Returns 201."""
    await _require_loan(loan_id, db)

    order = AppraisalOrder(
        id=uuid.uuid4(),
        loan_application_id=loan_id,
        property_id=body.property_id,
        appraiser_name=body.appraiser_name,
        appraiser_license=body.appraiser_license,
        appraiser_company=body.appraiser_company,
        order_date=body.order_date,
        due_date=body.due_date,
        status=body.status or "ORDERED",
        fee=body.fee,
        rush_fee=body.rush_fee,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return _order_to_response(order)


# ─── PUT /api/loans/{loan_id}/appraisal/{order_id} ───────────────────────────

@router.put(
    "/api/loans/{loan_id}/appraisal/{order_id}",
    response_model=AppraisalOrderResponse,
)
async def update_appraisal_order(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    body: AppraisalOrderUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """Update an appraisal order. Returns 200."""
    await _require_loan(loan_id, db)
    order = await _require_order(loan_id, order_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(order, field, value)
    order.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(order)
    return _order_to_response(order)


# ─── DELETE /api/loans/{loan_id}/appraisal/{order_id} ────────────────────────

@router.delete(
    "/api/loans/{loan_id}/appraisal/{order_id}",
    status_code=204,
)
async def delete_appraisal_order(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Delete an appraisal order and its reports. Returns 204."""
    await _require_loan(loan_id, db)
    order = await _require_order(loan_id, order_id, db)

    # Delete child reports (and their comparable sales via cascade)
    report_stmt = select(AppraisalReport).where(
        AppraisalReport.appraisal_order_id == order_id
    )
    reports = (await db.execute(report_stmt)).scalars().all()
    for report in reports:
        comp_stmt = select(ComparableSale).where(
            ComparableSale.appraisal_report_id == report.id
        )
        comps = (await db.execute(comp_stmt)).scalars().all()
        for comp in comps:
            await db.delete(comp)
        await db.delete(report)

    await db.delete(order)
    await db.commit()


# ─── GET /api/loans/{loan_id}/appraisal/{order_id}/report ────────────────────

@router.get(
    "/api/loans/{loan_id}/appraisal/{order_id}/report",
    response_model=List[AppraisalReportResponse],
)
async def list_appraisal_reports(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """List all appraisal reports for an order."""
    await _require_loan(loan_id, db)
    await _require_order(loan_id, order_id, db)

    stmt = (
        select(AppraisalReport)
        .where(AppraisalReport.appraisal_order_id == order_id)
        .order_by(AppraisalReport.created_at.desc())
    )
    reports = (await db.execute(stmt)).scalars().all()
    return [_report_to_response(r) for r in reports]


# ─── POST /api/loans/{loan_id}/appraisal/{order_id}/report ───────────────────

@router.post(
    "/api/loans/{loan_id}/appraisal/{order_id}/report",
    response_model=AppraisalReportResponse,
    status_code=201,
)
async def create_appraisal_report(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    body: AppraisalReportCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Submit an appraisal report for an order. Returns 201."""
    await _require_loan(loan_id, db)
    await _require_order(loan_id, order_id, db)

    report = AppraisalReport(
        id=uuid.uuid4(),
        appraisal_order_id=order_id,
        appraised_value=body.appraised_value,
        approach_used=body.approach_used,
        condition_rating=body.condition_rating,
        quality_rating=body.quality_rating,
        report_date=body.report_date,
        effective_date=body.effective_date,
        report_data=body.report_data,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return _report_to_response(report)


# ─── GET /api/loans/{loan_id}/appraisal/{order_id}/report/{report_id} ────────

@router.get(
    "/api/loans/{loan_id}/appraisal/{order_id}/report/{report_id}",
    response_model=AppraisalReportResponse,
)
async def get_appraisal_report(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """Get a single appraisal report by ID."""
    await _require_loan(loan_id, db)
    await _require_order(loan_id, order_id, db)
    report = await _require_report(order_id, report_id, db)
    return _report_to_response(report)


# ─── PUT /api/loans/{loan_id}/appraisal/{order_id}/report/{report_id} ────────

@router.put(
    "/api/loans/{loan_id}/appraisal/{order_id}/report/{report_id}",
    response_model=AppraisalReportResponse,
)
async def update_appraisal_report(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    report_id: uuid.UUID,
    body: AppraisalReportUpdate,
    db: AsyncSession = Depends(_get_db),
):
    """Update an appraisal report. Returns 200."""
    await _require_loan(loan_id, db)
    await _require_order(loan_id, order_id, db)
    report = await _require_report(order_id, report_id, db)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)

    await db.commit()
    await db.refresh(report)
    return _report_to_response(report)


# ─── GET /api/loans/{loan_id}/appraisal/{order_id}/report/{report_id}/comparables ──

@router.get(
    "/api/loans/{loan_id}/appraisal/{order_id}/report/{report_id}/comparables",
    response_model=List[ComparableSaleResponse],
)
async def list_comparable_sales(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
):
    """List all comparable sales for an appraisal report."""
    await _require_loan(loan_id, db)
    await _require_order(loan_id, order_id, db)
    await _require_report(order_id, report_id, db)

    stmt = (
        select(ComparableSale)
        .where(ComparableSale.appraisal_report_id == report_id)
        .order_by(ComparableSale.created_at)
    )
    comps = (await db.execute(stmt)).scalars().all()
    return [_comp_to_response(c) for c in comps]


# ─── POST /api/loans/{loan_id}/appraisal/{order_id}/report/{report_id}/comparables ──

@router.post(
    "/api/loans/{loan_id}/appraisal/{order_id}/report/{report_id}/comparables",
    response_model=ComparableSaleResponse,
    status_code=201,
)
async def create_comparable_sale(
    loan_id: uuid.UUID,
    order_id: uuid.UUID,
    report_id: uuid.UUID,
    body: ComparableSaleCreate,
    db: AsyncSession = Depends(_get_db),
):
    """Add a comparable sale to an appraisal report. Returns 201."""
    await _require_loan(loan_id, db)
    await _require_order(loan_id, order_id, db)
    await _require_report(order_id, report_id, db)

    comp = ComparableSale(
        id=uuid.uuid4(),
        appraisal_report_id=report_id,
        address=body.address,
        sale_price=body.sale_price,
        sale_date=body.sale_date,
        sqft=body.sqft,
        beds=body.beds,
        baths=body.baths,
        lot_size=body.lot_size,
        year_built=body.year_built,
        distance_miles=body.distance_miles,
        adjustments=body.adjustments,
        adjusted_price=body.adjusted_price,
        data_source=body.data_source,
        created_at=datetime.now(timezone.utc),
    )
    db.add(comp)
    await db.commit()
    await db.refresh(comp)
    return _comp_to_response(comp)
