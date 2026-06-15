"""
Rules API endpoints.

Endpoints:
- GET  /api/rules          — list all rules
- POST /api/rules          — create a new rule
- POST /api/rules/{id}     — update an existing rule
- POST /api/rules/{id}/toggle-active — toggle is_active flag
"""
from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.business_rule import BusinessRule
from app.repositories.rule_repository import RuleRepository
from app.schemas.rule import RuleCreateRequest, RuleResponse, RuleUpdateRequest

logger = structlog.get_logger()

router = APIRouter(prefix="/api/rules", tags=["rules"])


@router.get("", response_model=list[RuleResponse])
async def list_rules(db: AsyncSession = Depends(get_db)) -> list[RuleResponse]:
    """Return all business rules ordered by created_at desc."""
    repo = RuleRepository(db)
    rules = await repo.list_all()
    return [RuleResponse.model_validate(r) for r in rules]


@router.post("", response_model=RuleResponse, status_code=201)
async def create_rule(
    req: RuleCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    """Create a new business rule."""
    repo = RuleRepository(db)
    rule = BusinessRule(
        name=req.name,
        min_booking_value=req.min_booking_value,
        allowed_pickup_locations=req.allowed_pickup_locations,
        allowed_vehicle_categories=req.allowed_vehicle_categories,
        allowed_customer_categories=req.allowed_customer_categories,
        auto_accept=req.auto_accept,
        is_active=req.is_active,
    )
    rule = await repo.create(rule)
    await db.commit()
    logger.info("rule_created", id=str(rule.id), name=rule.name)
    return RuleResponse.model_validate(rule)


@router.post("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    req: RuleUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    """Update an existing rule. Only provided fields are changed."""
    try:
        rid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")

    repo = RuleRepository(db)
    rule = await repo.get_by_id(rid)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if req.name is not None:
        rule.name = req.name
    if req.min_booking_value is not None:
        rule.min_booking_value = req.min_booking_value
    if req.allowed_pickup_locations is not None:
        rule.allowed_pickup_locations = req.allowed_pickup_locations
    if req.allowed_vehicle_categories is not None:
        rule.allowed_vehicle_categories = req.allowed_vehicle_categories
    if req.allowed_customer_categories is not None:
        rule.allowed_customer_categories = req.allowed_customer_categories
    if req.auto_accept is not None:
        rule.auto_accept = req.auto_accept
    if req.is_active is not None:
        rule.is_active = req.is_active

    rule = await repo.save(rule)
    await db.commit()
    logger.info("rule_updated", id=str(rule.id), name=rule.name)
    return RuleResponse.model_validate(rule)


@router.post("/{rule_id}/toggle-active", response_model=RuleResponse)
async def toggle_rule_active(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
) -> RuleResponse:
    """Toggle the is_active flag of a rule."""
    try:
        rid = uuid.UUID(rule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid rule ID format")

    repo = RuleRepository(db)
    rule = await repo.get_by_id(rid)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    rule = await repo.save(rule)
    await db.commit()
    logger.info("rule_toggled", id=str(rule.id), is_active=rule.is_active)
    return RuleResponse.model_validate(rule)
