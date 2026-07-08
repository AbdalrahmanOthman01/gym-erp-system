import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.models_db import User, RoleEnum, UserStatusEnum, UserMembership, MembershipPlan, Product

notification_router = APIRouter(prefix="/notifications", tags=["Notifications"])

async def get_active_notifications_list(db: AsyncSession, current_user: User) -> List[Dict[str, Any]]:
    """
    Computes live system alerts dynamically from the database state.
    Filters demographics to respect gender boundaries if Accountant:
    - Male accountants see alerts regarding male members.
    - Female accountants see alerts regarding female members.
    - SuperAdmins see all alerts.
    """
    role = current_user.role
    gender_filter = None
    if role == RoleEnum.ACCOUNTANT_M:
        gender_filter = "male"
    elif role == RoleEnum.ACCOUNTANT_F:
        gender_filter = "female"

    alerts = []
    now = datetime.now()

    # 1. LOW STOCK NOTIFICATIONS
    # SuperAdmins see inventory warnings, Shift Accountants do not manage stock directly
    if role == RoleEnum.SUPERADMIN:
        prod_stmt = select(Product).where(Product.quantity <= 5, Product.is_deleted == False).order_by(Product.quantity.asc())
        prod_res = await db.execute(prod_stmt)
        for p in prod_res.scalars().all():
            alerts.append({
                "id": f"low_stock_{p.id}",
                "type": "low_stock",
                "severity": "warning",
                "title": f"Low Stock: {p.name}",
                "message": f"Only {p.quantity} units remaining in stock catalog. Reorder stock adjustments.",
                "action_url": "/inventory",
                "action_label": "Update Stock",
                "created_at": "Live Alert"
            })

    # 2. EXPIRED MEMBERSHIPS
    m_expired_stmt = select(User).where(
        User.role == RoleEnum.MEMBER,
        User.is_deleted == False,
        User.status == UserStatusEnum.EXPIRED
    )
    if gender_filter:
        m_expired_stmt = m_expired_stmt.where(User.gender == gender_filter)
    
    m_expired_res = await db.execute(m_expired_stmt)
    for m in m_expired_res.scalars().all():
        alerts.append({
            "id": f"expired_member_{m.id}",
            "type": "expired_member",
            "severity": "error",
            "title": f"Membership Expired",
            "message": f"Athlete '{m.full_name}' subscription terms have expired. Renew package.",
            "action_url": f"/dashboard?member_id={m.id}",
            "action_label": "View Profile",
            "created_at": "Critical Action"
        })

    # 3. EXPIRING SOON MEMBERSHIPS (Next 3 Days)
    expiring_soon_stmt = select(UserMembership).where(
        UserMembership.is_active == True,
        UserMembership.end_date >= now,
        UserMembership.end_date <= now + timedelta(days=3)
    ).options(selectinload(UserMembership.user))
    
    expiring_soon_res = await db.execute(expiring_soon_stmt)
    for sub in expiring_soon_res.scalars().all():
        user = sub.user
        if not user or user.is_deleted:
            continue
        if gender_filter and user.gender != gender_filter:
            continue
            
        days_left = (sub.end_date - now).days
        days_left = max(0, days_left)
        days_label = "today" if days_left == 0 else (f"tomorrow" if days_left == 1 else f"in {days_left} days")
        
        alerts.append({
            "id": f"expiring_soon_{sub.id}",
            "type": "expiring_soon",
            "severity": "warning",
            "title": "Membership Expiring Soon",
            "message": f"Athlete '{user.full_name}' membership expires {days_label} on {sub.end_date.strftime('%d %b %Y')}.",
            "action_url": f"/dashboard?member_id={user.id}",
            "action_label": "Renew Plan",
            "created_at": "Priority Alert"
        })

    # 4. BLOCKED ACCOUNTS
    m_blocked_stmt = select(User).where(
        User.role == RoleEnum.MEMBER,
        User.is_deleted == False,
        User.status == UserStatusEnum.BLOCKED
    )
    if gender_filter:
        m_blocked_stmt = m_blocked_stmt.where(User.gender == gender_filter)
        
    m_blocked_res = await db.execute(m_blocked_stmt)
    for m in m_blocked_res.scalars().all():
        alerts.append({
            "id": f"blocked_member_{m.id}",
            "type": "blocked_member",
            "severity": "info",
            "title": "Member Blocked",
            "message": f"Athlete '{m.full_name}' is administratively blocked. Access is denied.",
            "action_url": f"/dashboard?member_id={m.id}",
            "action_label": "View Profile",
            "created_at": "System Hold"
        })

    return alerts

@notification_router.get("", response_model=None)
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes a complete list of live operational warnings.
    """
    return await get_active_notifications_list(db, current_user)

@notification_router.get("/count", response_model=None)
async def get_notifications_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns only the count of active notifications for navbar badges.
    """
    alerts = await get_active_notifications_list(db, current_user)
    return {"count": len(alerts)}
