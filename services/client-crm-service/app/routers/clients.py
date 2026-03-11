"""
Client endpoints — /api/clients

CRUD for client records plus document sub-resource.
Write ownership: client-crm-service (post-Wave 2A cutover).

Security note: ssn_encrypted is accepted on create/update requests but is
NEVER returned in any response. The security review for SSN handling is
tracked separately (see doc/remaining-domains-inventory.md §3.2).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import Client, ClientDocument
from app.schemas import (
    ClientCreate,
    ClientDocumentCreate,
    ClientDocumentResponse,
    ClientResponse,
    ClientUpdate,
)

router = APIRouter(tags=["clients"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(client: Client) -> ClientResponse:
    return ClientResponse.model_validate(client, from_attributes=True)


async def _require_client(client_id: uuid.UUID, db: AsyncSession) -> Client:
    stmt = select(Client).where(Client.id == client_id)
    client = (await db.execute(stmt)).scalars().first()
    if client is None:
        raise HTTPException(status_code=404, detail=f"Client not found: {client_id}")
    return client


# ─── Client CRUD ──────────────────────────────────────────────────────────────

@router.get("/api/clients", response_model=List[ClientResponse])
async def list_clients(
    client_type: Optional[str] = None,
    assigned_agent_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List clients with optional filters."""
    stmt = select(Client)
    if client_type is not None:
        stmt = stmt.where(Client.client_type == client_type)
    if assigned_agent_id is not None:
        stmt = stmt.where(Client.assigned_agent_id == assigned_agent_id)
    stmt = stmt.order_by(Client.last_name, Client.first_name)
    clients = (await db.execute(stmt)).scalars().all()
    return [_to_response(c) for c in clients]


@router.get("/api/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get a client by ID."""
    return _to_response(await _require_client(client_id, db))


@router.post("/api/clients", response_model=ClientResponse, status_code=201)
async def create_client(
    body: ClientCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Create a new client. Returns 201 with created resource.
    SSN is not accepted via this endpoint per the security policy.
    """
    client = Client(
        id=uuid.uuid4(),
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        phone=body.phone,
        date_of_birth=body.date_of_birth,
        address_line1=body.address_line1,
        address_line2=body.address_line2,
        city=body.city,
        state=body.state,
        zip_code=body.zip_code,
        client_type=body.client_type or "BUYER",
        assigned_agent_id=body.assigned_agent_id,
        preferred_contact_method=body.preferred_contact_method,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return _to_response(client)


@router.put("/api/clients/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: uuid.UUID,
    body: ClientUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update a client. Returns 200 with updated resource."""
    client = await _require_client(client_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    client.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(client)
    return _to_response(client)


@router.delete("/api/clients/{client_id}", status_code=204)
async def delete_client(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete a client. Returns 204 No Content."""
    client = await _require_client(client_id, db)
    await db.delete(client)
    await db.commit()


# ─── Client Documents sub-resource ───────────────────────────────────────────

@router.get(
    "/api/clients/{client_id}/documents",
    response_model=List[ClientDocumentResponse],
)
async def list_client_documents(
    client_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List documents for a client."""
    await _require_client(client_id, db)
    stmt = select(ClientDocument).where(ClientDocument.client_id == client_id)
    docs = (await db.execute(stmt)).scalars().all()
    return [ClientDocumentResponse.model_validate(d, from_attributes=True) for d in docs]


@router.post(
    "/api/clients/{client_id}/documents",
    response_model=ClientDocumentResponse,
    status_code=201,
)
async def upload_client_document(
    client_id: uuid.UUID,
    body: ClientDocumentCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Record a document for a client. Returns 201 with created resource."""
    await _require_client(client_id, db)
    doc = ClientDocument(
        id=uuid.uuid4(),
        client_id=client_id,
        document_type=body.document_type,
        file_name=body.file_name,
        file_path=body.file_path,
        file_size_bytes=body.file_size_bytes,
        mime_type=body.mime_type,
        notes=body.notes,
        verified=False,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return ClientDocumentResponse.model_validate(doc, from_attributes=True)
