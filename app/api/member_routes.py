import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.core.dependencies import get_current_user, StrictGenderScopeValidator
from app.models.models_db import User, RoleEnum, UserStatusEnum, UserMembership, MembershipPlan, PaymentLog
from app.services.user_manager import UserManager

member_router = APIRouter(prefix="/members", tags=["Members"])

# Request Schemas
class MemberCreate(BaseModel):
    full_name: str
    phone: str
    gender: str # 'male' or 'female'
    weight: Optional[float] = None
    notes: Optional[str] = None
    plan_id: Optional[str] = None # Optional initial plan

class MemberUpdate(BaseModel):
    full_name: str
    phone: str
    gender: str
    weight: Optional[float] = None
    notes: Optional[str] = None

class MembershipEditPayload(BaseModel):
    plan_id: str
    start_date: str # YYYY-MM-DD format
    end_date: str # YYYY-MM-DD format
    remaining_sessions: Optional[int] = None
    paid_amount: float
    balance: float

class ActionNotes(BaseModel):
    notes: Optional[str] = None

@member_router.get("", response_model=None)
async def list_members(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Paginated members list. Enforces gender privacy boundaries:
    - Male staff see only males.
    - Female staff see only females.
    - Super Admins see all.
    """
    members = await UserManager.get_all_members(db, current_user, limit, offset, search)
    
    # Format return payload with basic details
    result = []
    for member in members:
        active_membership = next((m for m in member.memberships if m.is_active), None)
        plan_name = "No Active Plan"
        end_date_str = "N/A"
        remaining = "N/A"
        balance = 0.0
        paid_amount = 0.0
        
        if active_membership:
            plan_res = await db.execute(select(MembershipPlan).where(MembershipPlan.id == active_membership.plan_id))
            plan = plan_res.scalar_one_or_none()
            if plan:
                plan_name = plan.name
            end_date_str = active_membership.end_date.strftime("%d %b %Y") if active_membership.end_date else "Infinite"
            remaining = active_membership.remaining_sessions if active_membership.remaining_sessions is not None else "Unlimited"
            balance = float(active_membership.balance)
            paid_amount = float(active_membership.paid_amount)

        result.append({
            "id": str(member.id),
            "full_name": member.full_name,
            "phone": member.phone,
            "gender": member.gender,
            "weight": member.weight,
            "notes": member.notes,
            "status": member.status.value,
            "qr_uuid": str(member.qr_uuid),
            "join_date": member.join_date.strftime("%d %b %Y"),
            "plan_name": plan_name,
            "end_date": end_date_str,
            "remaining_sessions": remaining,
            "balance": balance,
            "paid_amount": paid_amount
        })
    return result

@member_router.post("", response_model=None)
async def create_member(
    payload: MemberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Creates a member and sets up their initial plan subscription if requested. """
    # Enforce RBAC gender bounds on create
    validator = StrictGenderScopeValidator()
    validator(payload.gender, current_user)

    # Check phone uniqueness
    existing_res = await db.execute(select(User).where(User.phone == payload.phone, User.is_deleted == False))
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Phone number is already registered.")

    # Save user record
    new_member = User(
        id=uuid.uuid4(),
        qr_uuid=uuid.uuid4(),
        full_name=payload.full_name,
        phone=payload.phone,
        gender=payload.gender,
        weight=payload.weight,
        notes=payload.notes,
        role=RoleEnum.MEMBER,
        status=UserStatusEnum.ACTIVE
    )
    db.add(new_member)
    await db.commit()

    # Create initial plan membership if requested
    if payload.plan_id:
        plan_res = await db.execute(select(MembershipPlan).where(MembershipPlan.id == uuid.UUID(payload.plan_id)))
        plan = plan_res.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Membership plan not found.")

        start_date = datetime.now()
        end_date = start_date + timedelta(days=plan.duration_days) if plan.duration_days else None

        new_membership = UserMembership(
            id=uuid.uuid4(),
            user_id=new_member.id,
            plan_id=plan.id,
            start_date=start_date,
            end_date=end_date,
            remaining_sessions=plan.sessions_limit,
            paid_amount=plan.price,
            balance=0.0,
            is_active=True
        )
        db.add(new_membership)

        # Log financial receipt as PaymentLog
        payment = PaymentLog(
            id=uuid.uuid4(),
            user_id=new_member.id,
            received_by=current_user.id,
            membership_id=new_membership.id,
            amount=plan.price,
            payment_method="Cash", # default cash register intake
            notes=f"Initial subscription registration: {plan.name}"
        )
        db.add(payment)
        await db.commit()

    return {"message": "Member registered successfully.", "member_id": str(new_member.id), "qr_uuid": str(new_member.qr_uuid)}

@member_router.get("/plans/active", response_model=None)
async def list_active_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Returns a list of active membership plans. """
    stmt = select(MembershipPlan).where(MembershipPlan.is_active == True).order_by(MembershipPlan.name.asc())
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
            "description": p.description
        } for p in plans
    ]

@member_router.get("/{member_id}", response_model=None)
async def get_member_detail(
    member_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Retrieves single member demographic data checking privacy bounds. """
    member_uuid = uuid.UUID(member_id)
    stmt = select(User).where(User.id == member_uuid, User.is_deleted == False).options(selectinload(User.memberships))
    res = await db.execute(stmt)
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    # Enforce RBAC privacy
    validator = StrictGenderScopeValidator()
    validator(member.gender, current_user)

    active_membership = next((m for m in member.memberships if m.is_active), None)
    plan_name = "No Active Plan"
    plan_id = ""
    plan_price = 0.0
    end_date_str = "N/A"
    remaining = "N/A"
    balance = 0.0
    paid_amount = 0.0
    start_date_str = "N/A"
    
    if active_membership:
        plan_res = await db.execute(select(MembershipPlan).where(MembershipPlan.id == active_membership.plan_id))
        plan = plan_res.scalar_one_or_none()
        if plan:
            plan_name = plan.name
            plan_id = str(plan.id)
            plan_price = float(plan.price)
        start_date_str = active_membership.start_date.strftime("%Y-%m-%d")
        end_date_str = active_membership.end_date.strftime("%Y-%m-%d") if active_membership.end_date else "Infinite"
        remaining = active_membership.remaining_sessions if active_membership.remaining_sessions is not None else "Unlimited"
        balance = float(active_membership.balance)
        paid_amount = float(active_membership.paid_amount)

    return {
        "id": str(member.id),
        "full_name": member.full_name,
        "phone": member.phone,
        "gender": member.gender,
        "weight": member.weight,
        "notes": member.notes,
        "status": member.status.value,
        "qr_uuid": str(member.qr_uuid),
        "join_date": member.join_date.strftime("%d %b %Y"),
        "plan_name": plan_name,
        "plan_id": plan_id,
        "plan_price": plan_price,
        "start_date": start_date_str,
        "end_date": end_date_str,
        "remaining_sessions": remaining,
        "balance": balance,
        "paid_amount": paid_amount
    }

@member_router.put("/{member_id}")
async def update_member(
    member_id: str,
    payload: MemberUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Updates member profile details. Enforces gender privacy boundaries. """
    member_uuid = uuid.UUID(member_id)
    res = await db.execute(select(User).where(User.id == member_uuid, User.is_deleted == False))
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    # Validate both existing gender scope and target updated gender scope
    validator = StrictGenderScopeValidator()
    validator(member.gender, current_user)
    validator(payload.gender, current_user)

    member.full_name = payload.full_name
    member.phone = payload.phone
    member.gender = payload.gender
    member.weight = payload.weight
    member.notes = payload.notes

    await db.commit()
    return {"message": "Member details updated successfully."}

@member_router.delete("/{member_id}")
async def delete_member(
    member_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Hard deletes user profile and related logs to remove from statistics. """
    member_uuid = uuid.UUID(member_id)
    res = await db.execute(select(User).where(User.id == member_uuid, User.is_deleted == False))
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    validator = StrictGenderScopeValidator()
    validator(member.gender, current_user)

    # 1. Delete Attendance Logs
    from app.models.models_db import AttendanceLog, BodyMeasurement, Sale
    from sqlalchemy import delete, update
    await db.execute(delete(AttendanceLog).where(AttendanceLog.member_id == member.id))

    # 2. Delete Body Measurements
    await db.execute(delete(BodyMeasurement).where(BodyMeasurement.user_id == member.id))

    # 3. Nullify Sale buyers (so we don't break POS records, but remove user reference)
    await db.execute(update(Sale).where(Sale.buyer_id == member.id).values(buyer_id=None))

    # 4. Delete Payment Logs
    await db.execute(delete(PaymentLog).where(PaymentLog.user_id == member.id))

    # 5. Delete Memberships
    await db.execute(delete(UserMembership).where(UserMembership.user_id == member.id))

    # 6. Hard delete the user record
    await db.execute(delete(User).where(User.id == member.id))

    await db.commit()
    return {"message": "Member record completely deleted."}

@member_router.put("/{member_id}/membership")
async def edit_member_membership(
    member_id: str,
    payload: MembershipEditPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Allows Super Administrators to modify/correct a member's active plan subscription. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only Super Administrators can edit active membership packages.")
    
    member_uuid = uuid.UUID(member_id)
    stmt = select(UserMembership).where(UserMembership.user_id == member_uuid, UserMembership.is_active == True)
    res = await db.execute(stmt)
    active_membership = res.scalar_one_or_none()

    if not active_membership:
        raise HTTPException(status_code=404, detail="No active membership found to edit.")

    try:
        start_dt = datetime.strptime(payload.start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(payload.end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    active_membership.plan_id = uuid.UUID(payload.plan_id)
    active_membership.start_date = start_dt
    active_membership.end_date = end_dt
    active_membership.remaining_sessions = payload.remaining_sessions
    active_membership.paid_amount = payload.paid_amount
    active_membership.balance = payload.balance

    await db.commit()
    return {"message": "Membership plan edited successfully."}

# ===============================================
# Admin Controls: Freeze, Block, Unfreeze, Unblock
# ===============================================

@member_router.post("/{member_id}/freeze")
async def freeze_member(
    member_id: str,
    payload: ActionNotes,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Pauses member subscription. Restricted to Super Admin. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only Super Administrators can freeze accounts.")
        
    member_uuid = uuid.UUID(member_id)
    res = await db.execute(select(User).where(User.id == member_uuid, User.is_deleted == False))
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    if member.status == UserStatusEnum.FROZEN:
         raise HTTPException(status_code=400, detail="Account is already frozen.")

    member.status = UserStatusEnum.FROZEN
    member.frozen_at = datetime.now()
    await db.commit()

    return {"message": "Member account frozen successfully.", "frozen_at": member.frozen_at.strftime("%d %b %Y")}

@member_router.post("/{member_id}/unfreeze")
async def unfreeze_member(
    member_id: str,
    payload: ActionNotes,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Manually unpauses member subscription and recalculates extensions. Restricted to Super Admin. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only Super Administrators can unfreeze accounts.")
        
    member_uuid = uuid.UUID(member_id)
    res = await db.execute(select(User).where(User.id == member_uuid, User.is_deleted == False).options(selectinload(User.memberships)))
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    if member.status != UserStatusEnum.FROZEN:
         raise HTTPException(status_code=400, detail="Account is not frozen.")

    active_plan = next((m for m in member.memberships if m.is_active), None)
    
    # Recalculate and push active_plan.end_date forward
    if member.frozen_at and active_plan and active_plan.end_date:
        days_frozen = (datetime.now() - member.frozen_at).days
        days_frozen = max(1, days_frozen)
        active_plan.end_date += timedelta(days=days_frozen)

    member.status = UserStatusEnum.ACTIVE
    member.frozen_at = None
    await db.commit()

    return {"message": "Member account unfrozen successfully and membership extended."}

@member_router.post("/{member_id}/block")
async def block_member(
    member_id: str,
    payload: ActionNotes,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Administratively blocks member access. Restricted to Super Admin. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only Super Administrators can block accounts.")
        
    member_uuid = uuid.UUID(member_id)
    res = await db.execute(select(User).where(User.id == member_uuid, User.is_deleted == False))
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    member.status = UserStatusEnum.BLOCKED
    await db.commit()

    return {"message": "Member account blocked successfully."}

@member_router.post("/{member_id}/unblock")
async def unblock_member(
    member_id: str,
    payload: ActionNotes,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Administratively unblocks member access. Restricted to Super Admin. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=403, detail="Only Super Administrators can unblock accounts.")
        
    member_uuid = uuid.UUID(member_id)
    res = await db.execute(select(User).where(User.id == member_uuid, User.is_deleted == False))
    member = res.scalar_one_or_none()

    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    member.status = UserStatusEnum.ACTIVE
    await db.commit()

    return {"message": "Member account unblocked successfully."}
