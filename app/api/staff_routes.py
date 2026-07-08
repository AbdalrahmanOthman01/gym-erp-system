import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.core.dependencies import get_current_active_superuser
from app.models.models_db import User, RoleEnum, UserStatusEnum
from app.core.security import get_password_hash

staff_router = APIRouter(prefix="/staff", tags=["Staff Management"])

# Request/Response Schemas
class StaffCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=1, max_length=20)
    gender: str = Field(..., pattern="^(male|female)$")
    role: RoleEnum
    password: str = Field(..., min_length=6)

class StaffUpdate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=1, max_length=20)
    gender: str = Field(..., pattern="^(male|female)$")
    role: RoleEnum
    password: Optional[str] = Field(None, min_length=6)

@staff_router.get("", response_model=None)
async def list_staff(
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all administrative and accounting staff members in the system.
    Members (gym clients) are excluded.
    """
    stmt = select(User).where(
        User.role != RoleEnum.MEMBER,
        User.is_deleted == False
    ).order_by(User.join_date.desc())
    res = await db.execute(stmt)
    staff_members = res.scalars().all()
    
    return [
        {
            "id": str(s.id),
            "full_name": s.full_name,
            "phone": s.phone,
            "gender": s.gender,
            "role": s.role.value,
            "status": s.status.value,
            "join_date": s.join_date.strftime("%d %b %Y") if s.join_date else None
        } for s in staff_members
    ]

@staff_router.post("", response_model=None)
async def create_staff(
    payload: StaffCreate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new staff profile (SuperAdmin or Accountant) and persists it.
    """
    if payload.role == RoleEnum.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot register a standard gym member using the staff management interface."
        )

    # Check phone uniqueness across active users
    existing_res = await db.execute(
        select(User).where(User.phone == payload.phone, User.is_deleted == False)
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this phone number is already registered."
        )

    # Instantiate staff user
    new_staff = User(
        id=uuid.uuid4(),
        qr_uuid=uuid.uuid4(),
        full_name=payload.full_name,
        phone=payload.phone,
        hashed_password=get_password_hash(payload.password),
        gender=payload.gender,
        role=payload.role,
        status=UserStatusEnum.ACTIVE
    )
    db.add(new_staff)
    await db.commit()
    
    return {"message": "Staff member created successfully.", "staff_id": str(new_staff.id)}

@staff_router.put("/{staff_id}", response_model=None)
async def update_staff(
    staff_id: str,
    payload: StaffUpdate,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    Modifies staff details (Name, Phone, Role, Gender) and optionally updates password.
    """
    staff_uuid = uuid.UUID(staff_id)
    res = await db.execute(select(User).where(User.id == staff_uuid, User.is_deleted == False))
    staff = res.scalar_one_or_none()
    
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff profile not found."
        )
        
    if staff.role == RoleEnum.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target profile is a gym member. Use members management interface to update."
        )

    if payload.role == RoleEnum.MEMBER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign MEMBER role to staff profiles."
        )

    # Verify phone uniqueness if altered
    if staff.phone != payload.phone:
        existing_res = await db.execute(
            select(User).where(User.phone == payload.phone, User.is_deleted == False)
        )
        if existing_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Another user is already registered with this phone number."
            )

    staff.full_name = payload.full_name
    staff.phone = payload.phone
    staff.gender = payload.gender
    staff.role = payload.role
    
    # Hash password if reset is requested
    if payload.password:
        staff.hashed_password = get_password_hash(payload.password)
        
    await db.commit()
    return {"message": "Staff member updated successfully."}

@staff_router.delete("/{staff_id}", response_model=None)
async def delete_staff(
    staff_id: str,
    current_user: User = Depends(get_current_active_superuser),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft-deletes a staff profile, restricting login access.
    """
    staff_uuid = uuid.UUID(staff_id)
    res = await db.execute(select(User).where(User.id == staff_uuid, User.is_deleted == False))
    staff = res.scalar_one_or_none()
    
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff profile not found."
        )

    # Cannot delete oneself
    if staff.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security safeguard: You cannot delete your own active administrator account."
        )

    staff.is_deleted = True
    staff.deleted_at = datetime.now()
    staff.deleted_by = current_user.id
    
    await db.commit()
    return {"message": "Staff member soft-deleted successfully."}
