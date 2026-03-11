"""
Closing document endpoints.

Implements CRUD routes under /api/closings/{closing_id}/documents.
The closing-service owns write access to closing_documents after Wave 3 cutover.
"""
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import ClosingDetail, ClosingDocument
from app.schemas import (
    ClosingDocumentCreate,
    ClosingDocumentResponse,
    ClosingDocumentUpdate,
)

router = APIRouter(tags=["closing-documents"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


# Placeholder dependency — overridden in main.py via dependency_overrides
async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(doc: ClosingDocument) -> ClosingDocumentResponse:
    return ClosingDocumentResponse.model_validate(doc, from_attributes=True)


async def _require_closing(closing_id: uuid.UUID, db: AsyncSession) -> ClosingDetail:
    stmt = select(ClosingDetail).where(ClosingDetail.id == closing_id)
    closing = (await db.execute(stmt)).scalars().first()
    if closing is None:
        raise HTTPException(status_code=404, detail=f"Closing not found: {closing_id}")
    return closing


# ─── GET /api/closings/{closing_id}/documents ─────────────────────────────────

@router.get(
    "/api/closings/{closing_id}/documents",
    response_model=List[ClosingDocumentResponse],
)
async def list_documents(
    closing_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List all documents for a closing."""
    await _require_closing(closing_id, db)
    stmt = (
        select(ClosingDocument)
        .where(ClosingDocument.closing_id == closing_id)
        .order_by(ClosingDocument.created_at.desc())
    )
    docs = (await db.execute(stmt)).scalars().all()
    return [_to_response(d) for d in docs]


# ─── GET /api/closings/{closing_id}/documents/{doc_id} ────────────────────────

@router.get(
    "/api/closings/{closing_id}/documents/{doc_id}",
    response_model=ClosingDocumentResponse,
)
async def get_document(
    closing_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a single closing document by ID."""
    await _require_closing(closing_id, db)
    stmt = select(ClosingDocument).where(
        ClosingDocument.id == doc_id,
        ClosingDocument.closing_id == closing_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Closing document not found: {doc_id}")
    return _to_response(doc)


# ─── POST /api/closings/{closing_id}/documents ────────────────────────────────

@router.post(
    "/api/closings/{closing_id}/documents",
    response_model=ClosingDocumentResponse,
    status_code=201,
)
async def create_document(
    closing_id: uuid.UUID,
    body: ClosingDocumentCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Add a document to a closing. Returns 201 with created resource."""
    await _require_closing(closing_id, db)

    doc = ClosingDocument(
        id=uuid.uuid4(),
        closing_id=closing_id,
        document_type=body.document_type,
        file_name=body.file_name,
        file_path=body.file_path,
        file_size_bytes=body.file_size_bytes,
        signed=body.signed or False,
        signed_date=body.signed_date,
        signed_by=body.signed_by,
        notarized=body.notarized or False,
        notary_name=body.notary_name,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _to_response(doc)


# ─── PUT /api/closings/{closing_id}/documents/{doc_id} ────────────────────────

@router.put(
    "/api/closings/{closing_id}/documents/{doc_id}",
    response_model=ClosingDocumentResponse,
)
async def update_document(
    closing_id: uuid.UUID,
    doc_id: uuid.UUID,
    body: ClosingDocumentUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update a closing document. Returns 200 with updated resource."""
    await _require_closing(closing_id, db)
    stmt = select(ClosingDocument).where(
        ClosingDocument.id == doc_id,
        ClosingDocument.closing_id == closing_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Closing document not found: {doc_id}")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(doc, field, value)

    await db.commit()
    await db.refresh(doc)
    return _to_response(doc)


# ─── DELETE /api/closings/{closing_id}/documents/{doc_id} ────────────────────

@router.delete(
    "/api/closings/{closing_id}/documents/{doc_id}",
    status_code=204,
)
async def delete_document(
    closing_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete a closing document. Returns 204 No Content."""
    await _require_closing(closing_id, db)
    stmt = select(ClosingDocument).where(
        ClosingDocument.id == doc_id,
        ClosingDocument.closing_id == closing_id,
    )
    doc = (await db.execute(stmt)).scalars().first()
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Closing document not found: {doc_id}")

    await db.delete(doc)
    await db.commit()
