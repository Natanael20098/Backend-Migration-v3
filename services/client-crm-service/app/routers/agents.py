"""
Agent endpoints — /api/agents

CRUD for agent records plus agent license and commission sub-resources.
Write ownership: client-crm-service (post-Wave 2A cutover).
"""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import make_get_current_user
from app.config import settings
from app.models import Agent, AgentLicense, Commission
from app.schemas import (
    AgentCreate,
    AgentLicenseCreate,
    AgentLicenseResponse,
    AgentResponse,
    AgentUpdate,
    CommissionCreate,
    CommissionResponse,
)

router = APIRouter(tags=["agents"])

_get_current_user = make_get_current_user(settings.JWT_SECRET)


async def _get_db() -> AsyncSession:  # pragma: no cover
    raise NotImplementedError("DB dependency not wired")


def _to_response(agent: Agent) -> AgentResponse:
    return AgentResponse.model_validate(agent, from_attributes=True)


async def _require_agent(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    stmt = select(Agent).where(Agent.id == agent_id)
    agent = (await db.execute(stmt)).scalars().first()
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return agent


# ─── Agent CRUD ───────────────────────────────────────────────────────────────

@router.get("/api/agents", response_model=List[AgentResponse])
async def list_agents(
    brokerage_id: Optional[uuid.UUID] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List agents with optional filters."""
    stmt = select(Agent)
    if brokerage_id is not None:
        stmt = stmt.where(Agent.brokerage_id == brokerage_id)
    if is_active is not None:
        stmt = stmt.where(Agent.is_active == is_active)
    stmt = stmt.order_by(Agent.last_name, Agent.first_name)
    agents = (await db.execute(stmt)).scalars().all()
    return [_to_response(a) for a in agents]


@router.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Get an agent by ID."""
    return _to_response(await _require_agent(agent_id, db))


@router.post("/api/agents", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Create a new agent. Returns 201 with created resource."""
    if body.email:
        existing = (
            await db.execute(select(Agent).where(Agent.email == body.email))
        ).scalars().first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Email already in use: {body.email}")

    agent = Agent(
        id=uuid.uuid4(),
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        phone=body.phone,
        license_number=body.license_number,
        brokerage_id=body.brokerage_id,
        hire_date=body.hire_date,
        is_active=body.is_active if body.is_active is not None else True,
        commission_rate=body.commission_rate,
        bio=body.bio,
        photo_url=body.photo_url,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return _to_response(agent)


@router.put("/api/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: uuid.UUID,
    body: AgentUpdate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Update an agent. Returns 200 with updated resource."""
    agent = await _require_agent(agent_id, db)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    agent.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(agent)
    return _to_response(agent)


@router.delete("/api/agents/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Delete an agent. Returns 204 No Content."""
    agent = await _require_agent(agent_id, db)
    await db.delete(agent)
    await db.commit()


# ─── Agent Licenses sub-resource ─────────────────────────────────────────────

@router.get("/api/agents/{agent_id}/licenses", response_model=List[AgentLicenseResponse])
async def list_agent_licenses(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List licenses for an agent."""
    await _require_agent(agent_id, db)
    stmt = select(AgentLicense).where(AgentLicense.agent_id == agent_id)
    licenses = (await db.execute(stmt)).scalars().all()
    return [AgentLicenseResponse.model_validate(l, from_attributes=True) for l in licenses]


@router.post(
    "/api/agents/{agent_id}/licenses",
    response_model=AgentLicenseResponse,
    status_code=201,
)
async def add_agent_license(
    agent_id: uuid.UUID,
    body: AgentLicenseCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Add a license to an agent. Returns 201 with created resource."""
    await _require_agent(agent_id, db)
    license_ = AgentLicense(
        id=uuid.uuid4(),
        agent_id=agent_id,
        license_type=body.license_type,
        license_number=body.license_number,
        state=body.state,
        issue_date=body.issue_date,
        expiry_date=body.expiry_date,
        status=body.status or "ACTIVE",
        created_at=datetime.now(timezone.utc),
    )
    db.add(license_)
    await db.commit()
    await db.refresh(license_)
    return AgentLicenseResponse.model_validate(license_, from_attributes=True)


# ─── Agent Commissions sub-resource ──────────────────────────────────────────

@router.get("/api/agents/{agent_id}/commissions", response_model=List[CommissionResponse])
async def list_agent_commissions(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """List commissions for an agent."""
    await _require_agent(agent_id, db)
    stmt = select(Commission).where(Commission.agent_id == agent_id)
    commissions = (await db.execute(stmt)).scalars().all()
    return [CommissionResponse.model_validate(c, from_attributes=True) for c in commissions]


@router.post(
    "/api/agents/{agent_id}/commissions",
    response_model=CommissionResponse,
    status_code=201,
)
async def create_agent_commission(
    agent_id: uuid.UUID,
    body: CommissionCreate,
    db: AsyncSession = Depends(_get_db),
    _: str = Depends(_get_current_user),
):
    """Record a commission for an agent. Returns 201 with created resource."""
    await _require_agent(agent_id, db)
    commission = Commission(
        id=uuid.uuid4(),
        agent_id=agent_id,
        listing_id=body.listing_id,
        transaction_id=body.transaction_id,
        amount=body.amount,
        commission_rate=body.commission_rate,
        type=body.type,
        status=body.status or "PENDING",
        paid_date=body.paid_date,
        notes=body.notes,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(commission)
    await db.commit()
    await db.refresh(commission)
    return CommissionResponse.model_validate(commission, from_attributes=True)
