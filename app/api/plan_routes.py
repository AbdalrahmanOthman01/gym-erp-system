import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.core.dependencies import get_current_user, get_current_active_superuser
from app.models.models_db import User, MembershipPlan

plan_router = APIRouter(prefix="/plans", tags=["Membership Plans"])

# Request Schemas
class PlanCreate(BaseModel):
    name: str = Field(..., max_length=100)
    price: float = Field(..., ge=0.0)
    duration_days: Optional[int] = Field(None, ge=1)
    sessions_limit: Optional[int] = Field(None, ge=1)
    freeze_days: int = Field(0, ge=0)
    description: Optional[str] = Field(None, max_length=255)

class PlanUpdate(BaseModel):
    name: str = Field(..., max_length=100)
    price: float = Field(..., ge=0.0)
    duration_days: Optional[int] = Field(None, ge=1)
    sessions_limit: Optional[int] = Field(None, ge=1)
    freeze_days: int = Field(0, ge=0)
    description: Optional[str] = Field(None, max_length=255)
    is_active: bool = Field(True)

@plan_router.get("", response_model=None)
async def list_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all membership plans in the database.
    Ordered by is_active (active first) and then by name.
    """
    stmt = select(MembershipPlan).order_by(MembershipPlan.is_active.desc(), MembershipPlan.name.asc())
    res = await db.execute(stmt)
    plans = res.scalars().all()
    
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "price": float(p.price),
            "duration_days": p.duration_days,
            "sessions_limit": p.sessions_limit,
            "freeze_days": p.freeze_days,
            "description": p.description,
            "is_active": p.is_active,
            "created_at": p.created_at.strftime("%d %b %Y") if p.created_at else None
        } for p in plans
    ]

@plan_router.post("", response_model=None)
async def create_plan(
    payload: PlanCreate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new membership plan template.
    Restricted to Super Administrators.
    """
    # Check name uniqueness
    existing_res = await db.execute(
        select(MembershipPlan).where(MembershipPlan.name.ilike(payload.name))
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A membership plan with this name already exists."
        )
        
    plan = MembershipPlan(
        id=uuid.uuid4(),
        name=payload.name,
        price=payload.price,
        duration_days=payload.duration_days,
        sessions_limit=payload.sessions_limit,
        freeze_days=payload.freeze_days,
        description=payload.description,
        is_active=True
    )
    db.add(plan)
    await db.commit()
    
    return {"message": "Membership plan created successfully.", "plan_id": str(plan.id)}

@plan_router.put("/{plan_id}", response_model=None)
async def update_plan(
    plan_id: str,
    payload: PlanUpdate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates an existing membership plan configuration.
    Restricted to Super Administrators.
    """
    plan_uuid = uuid.UUID(plan_id)
    res = await db.execute(select(MembershipPlan).where(MembershipPlan.id == plan_uuid))
    plan = res.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found."
        )
        
    # Check uniqueness of name if changed
    if plan.name.lower() != payload.name.lower():
        existing_res = await db.execute(
            select(MembershipPlan).where(MembershipPlan.name.ilike(payload.name))
        )
        if existing_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another membership plan is already using this name."
            )
            
    plan.name = payload.name
    plan.price = payload.price
    plan.duration_days = payload.duration_days
    plan.sessions_limit = payload.sessions_limit
    plan.freeze_days = payload.freeze_days
    plan.description = payload.description
    plan.is_active = payload.is_active
    
    await db.commit()
    return {"message": "Membership plan updated successfully."}

@plan_router.delete("/{plan_id}", response_model=None)
async def delete_plan(
    plan_id: str,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivates a membership plan (soft delete).
    Restricted to Super Administrators.
    """
    plan_uuid = uuid.UUID(plan_id)
    res = await db.execute(select(MembershipPlan).where(MembershipPlan.id == plan_uuid))
    plan = res.scalar_one_or_none()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership plan not found."
        )
        
    plan.is_active = False
    await db.commit()
    
    return {"message": "Membership plan deactivated successfully."}
