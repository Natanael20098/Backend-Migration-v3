"""
Title report endpoints.

Implements CRUD routes under /api/closings/{closing_id}/title-report.
The closing-service owns write access to title_reports after Wave 3 cutover.
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import ClosingDetail, TitleReport
from app.schemas import (
    TitleReportCreate,
    TitleReportResponse,
    TitleReportUpdate,
)

router = APIRouter(tags=["title-reports"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(report: TitleReport) -> TitleReportResponse:
    return TitleReportResponse.model_validate(report, from_attributes=True)


async def _require_closing(closing_id: uuid.UUID, db: AsyncSession) -> ClosingDetail:
    stmt = select(ClosingDetail).where(ClosingDetail.id == closing_id)
    closing = (await db.execute(stmt)).scalars().first()
    if closing is None:
        raise HTTPException(status_code=404, detail=f"Closing not found: {closing_id}")
    return closing


# ─── GET /api/closings/{closing_id}/title-report ──────────────────────────────

@router.get(
    "/api/closings/{closing_id}/title-report",
    response_model=List[TitleReportResponse],
)
async def list_title_reports(
    closing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List all title reports for a closing."""
    await _require_closing(closing_id, db)
    stmt = (
        select(TitleReport)
        .where(TitleReport.closing_id == closing_id)
        .order_by(TitleReport.created_at.desc())
    )
    reports = (await db.execute(stmt)).scalars().all()
    return [_to_response(r) for r in reports]


# ─── GET /api/closings/{closing_id}/title-report/{report_id} ─────────────────

@router.get(
    "/api/closings/{closing_id}/title-report/{report_id}",
    response_model=TitleReportResponse,
)
async def get_title_report(
    closing_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a single title report by ID."""
    await _require_closing(closing_id, db)
    stmt = select(TitleReport).where(
        TitleReport.id == report_id,
        TitleReport.closing_id == closing_id,
    )
    report = (await db.execute(stmt)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Title report not found: {report_id}")
    return _to_response(report)


# ─── POST /api/closings/{closing_id}/title-report ─────────────────────────────

@router.post(
    "/api/closings/{closing_id}/title-report",
    response_model=TitleReportResponse,
    status_code=201,
)
async def create_title_report(
    closing_id: uuid.UUID,
    body: TitleReportCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Create a title report for a closing. Returns 201 with created resource."""
    await _require_closing(closing_id, db)

    report = TitleReport(
        id=uuid.uuid4(),
        closing_id=closing_id,
        title_company=body.title_company,
        title_number=body.title_number,
        status=body.status or "PENDING",
        issues=body.issues,
        lien_amount=body.lien_amount,
        report_date=body.report_date,
        effective_date=body.effective_date,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return _to_response(report)


# ─── PUT /api/closings/{closing_id}/title-report/{report_id} ─────────────────

@router.put(
    "/api/closings/{closing_id}/title-report/{report_id}",
    response_model=TitleReportResponse,
)
async def update_title_report(
    closing_id: uuid.UUID,
    report_id: uuid.UUID,
    body: TitleReportUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update a title report. Returns 200 with updated resource."""
    await _require_closing(closing_id, db)
    stmt = select(TitleReport).where(
        TitleReport.id == report_id,
        TitleReport.closing_id == closing_id,
    )
    report = (await db.execute(stmt)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Title report not found: {report_id}")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(report, field, value)
    report.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(report)
    return _to_response(report)


# ─── DELETE /api/closings/{closing_id}/title-report/{report_id} ──────────────

@router.delete(
    "/api/closings/{closing_id}/title-report/{report_id}",
    status_code=204,
)
async def delete_title_report(
    closing_id: uuid.UUID,
    report_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete a title report. Returns 204 No Content."""
    await _require_closing(closing_id, db)
    stmt = select(TitleReport).where(
        TitleReport.id == report_id,
        TitleReport.closing_id == closing_id,
    )
    report = (await db.execute(stmt)).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail=f"Title report not found: {report_id}")

    await db.delete(report)
    await db.commit()
