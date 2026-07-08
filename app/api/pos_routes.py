import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.core.dependencies import get_current_user, StrictGenderScopeValidator
from app.models.models_db import User, RoleEnum, PaymentLog, Sale, SaleItem, Product, UserMembership, MembershipPlan, Expense
from app.services.pos_svc import POSService

pos_router = APIRouter(tags=["POS & Ledger"])

# Request Schemas
class POSCartItem(BaseModel):
    product_id: str
    quantity: int = Field(..., gt=0)

class POSSalePayload(BaseModel):
    buyer_id: Optional[str] = None # Member ID
    items: List[POSCartItem]
    payment_method: str = Field(..., max_length=50) # 'Cash', 'Card'

class ManualPaymentPayload(BaseModel):
    member_id: str
    amount: float = Field(..., gt=0.0)
    payment_method: str
    notes: Optional[str] = None
    plan_id: Optional[str] = None # if registering/renewing a subscription
    start_date: Optional[str] = None # YYYY-MM-DD format for custom start dates

class ExpenseCreate(BaseModel):
    amount: float = Field(..., gt=0.0)
    category: str = Field(..., max_length=100)
    notes: Optional[str] = Field(None, max_length=255)

@pos_router.post("/pos/sale", response_model=None)
async def process_pos_sale(
    payload: POSSalePayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Processes cart checkout, updates inventory, and broadcasts live. """
    buyer_uuid = None
    if payload.buyer_id:
        buyer_uuid = uuid.UUID(payload.buyer_id)
        # Fetch buyer gender to enforce RBAC middleware
        buyer_res = await db.execute(select(User).where(User.id == buyer_uuid))
        buyer_user = buyer_res.scalar_one_or_none()
        if not buyer_user:
            raise HTTPException(status_code=404, detail="Gym member not found.")
            
        validator = StrictGenderScopeValidator()
        validator(buyer_user.gender, current_user)

    items_dict = [{"product_id": x.product_id, "quantity": x.quantity} for x in payload.items]
    
    sale_record = await POSService.process_product_sale(
        db=db,
        seller_id=current_user.id,
        buyer_id=buyer_uuid,
        items_payload=items_dict,
        payment_method=payload.payment_method
    )

    return {"message": "POS Transaction completed successfully.", "sale_id": str(sale_record.id)}

@pos_router.post("/payments/manual", response_model=None)
async def log_manual_payment(
    payload: ManualPaymentPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Logs manual payments (like membership renewals) and activates subscriptions. """
    member_uuid = uuid.UUID(payload.member_id)
    member_res = await db.execute(select(User).where(User.id == member_uuid, User.is_deleted == False))
    member = member_res.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found.")

    # Enforce RBAC gender bounds
    validator = StrictGenderScopeValidator()
    validator(member.gender, current_user)

    target_membership_id = None

    # If renewal/plan activation requested
    if payload.plan_id:
        plan_uuid = uuid.UUID(payload.plan_id)
        plan_res = await db.execute(select(MembershipPlan).where(MembershipPlan.id == plan_uuid))
        plan = plan_res.scalar_one_or_none()
        if not plan:
            raise HTTPException(status_code=404, detail="Membership plan not found.")

        # Deactivate old memberships
        old_mems = await db.execute(select(UserMembership).where(UserMembership.user_id == member.id))
        for m in old_mems.scalars().all():
            m.is_active = False

        start_date = datetime.now()
        if payload.start_date:
            try:
                start_date = datetime.strptime(payload.start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start date format. Use YYYY-MM-DD")

        end_date = start_date + timedelta(days=plan.duration_days) if plan.duration_days else None

        # Installments balance tracking
        plan_price = float(plan.price)
        membership_balance = max(0.0, plan_price - payload.amount)

        new_sub = UserMembership(
            id=uuid.uuid4(),
            user_id=member.id,
            plan_id=plan.id,
            start_date=start_date,
            end_date=end_date,
            remaining_sessions=plan.sessions_limit,
            paid_amount=payload.amount,
            balance=membership_balance,
            is_active=True
        )
        db.add(new_sub)
        target_membership_id = new_sub.id

        # Force user status to active since they renewed
        member.status = UserStatusEnum.ACTIVE
        member.frozen_at = None
    else:
        # Check if paying an installment on their active plan
        active_sub_stmt = select(UserMembership).where(
            UserMembership.user_id == member.id,
            UserMembership.is_active == True
        )
        res = await db.execute(active_sub_stmt)
        active_membership = res.scalar_one_or_none()

        if active_membership and float(active_membership.balance) > 0:
            new_balance = float(active_membership.balance) - payload.amount
            active_membership.balance = max(0.0, new_balance)
            active_membership.paid_amount = float(active_membership.paid_amount) + payload.amount
            target_membership_id = active_membership.id

    payment = PaymentLog(
        id=uuid.uuid4(),
        user_id=member.id,
        received_by=current_user.id,
        membership_id=target_membership_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        notes=payload.notes or "Manual financial deposit logged."
    )
    db.add(payment)
    await db.commit()

    # Broadcast revenue update to WS
    from app.api.websockets import manager
    await manager.broadcast({
        "event": "NEW_PAYMENT",
        "member_name": member.full_name,
        "amount": payload.amount,
        "payment_method": payload.payment_method,
        "timestamp": "Just Now"
    })

    return {"message": "Payment logged successfully and subscription processed."}

@pos_router.get("/payments/ledger", response_model=None)
async def list_financial_ledger(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns unified chronological transaction log of both POS sales,
    manual membership payments, and general gym expenses.
    """
    # Fetch Payment Logs
    p_stmt = select(PaymentLog).order_by(PaymentLog.payment_date.desc()).limit(limit)
    p_res = await db.execute(p_stmt)
    payment_logs = p_res.scalars().all()

    # Fetch POS Sales
    s_stmt = select(Sale).order_by(Sale.created_at.desc()).limit(limit).options(selectinload(Sale.buyer), selectinload(Sale.seller))
    s_res = await db.execute(s_stmt)
    sales = s_res.scalars().all()

    # Fetch Expenses
    e_stmt = select(Expense).order_by(Expense.created_at.desc()).limit(limit)
    e_res = await db.execute(e_stmt)
    expenses = e_res.scalars().all()

    unified_ledger = []

    # Map manual payments
    for log in payment_logs:
        member_res = await db.execute(select(User).where(User.id == log.user_id))
        member = member_res.scalar_one_or_none()
        
        staff_res = await db.execute(select(User).where(User.id == log.received_by))
        staff = staff_res.scalar_one_or_none()
        
        if current_user.role != RoleEnum.SUPERADMIN:
            allowed_gender = "male" if current_user.role == RoleEnum.ACCOUNTANT_M else "female"
            if member and member.gender != allowed_gender:
                continue
                
        unified_ledger.append({
            "id": str(log.id),
            "type": "Membership Payment",
            "member_name": member.full_name if member else "Unknown Member",
            "phone": member.phone if member else "N/A",
            "amount": float(log.amount),
            "profit": float(log.amount),
            "payment_method": log.payment_method,
            "processed_by": staff.full_name if staff else "Staff",
            "timestamp": log.payment_date.strftime("%d %b %Y, %I:%M %p"),
            "notes": log.notes or "N/A"
        })

    # Map POS sales
    for sale in sales:
        if current_user.role != RoleEnum.SUPERADMIN:
            allowed_gender = "male" if current_user.role == RoleEnum.ACCOUNTANT_M else "female"
            if sale.buyer and sale.buyer.gender != allowed_gender:
                continue

        unified_ledger.append({
            "id": str(sale.id),
            "type": "Merchandise POS",
            "member_name": sale.buyer.full_name if sale.buyer else "Walk-in Guest",
            "phone": sale.buyer.phone if sale.buyer else "N/A",
            "amount": float(sale.total_amount),
            "profit": round(float(sale.total_amount) - float(sale.total_cost), 2),
            "payment_method": sale.payment_method,
            "processed_by": sale.seller.full_name if sale.seller else "Staff",
            "timestamp": sale.created_at.strftime("%d %b %Y, %I:%M %p"),
            "notes": "POS Checkout"
        })

    # Map general expenses
    for exp in expenses:
        unified_ledger.append({
            "id": str(exp.id),
            "type": "Expense Outflow",
            "member_name": f"N/A ({exp.category})",
            "phone": "N/A",
            "amount": float(exp.amount),
            "profit": -float(exp.amount),
            "payment_method": "Outflow",
            "processed_by": "System",
            "timestamp": exp.created_at.strftime("%d %b %Y, %I:%M %p"),
            "notes": exp.notes or "Gym Expense"
        })

    # Sort unified ledger chronologically (newest first)
    unified_ledger.sort(key=lambda x: datetime.strptime(x["timestamp"], "%d %b %Y, %I:%M %p"), reverse=True)
    
    return unified_ledger[:limit]

@pos_router.post("/expenses", response_model=None)
async def create_expense(
    payload: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Logs a gym expense outflow. """
    new_expense = Expense(
        id=uuid.uuid4(),
        amount=payload.amount,
        category=payload.category,
        notes=payload.notes
    )
    db.add(new_expense)
    await db.commit()
    return {"message": "Expense logged successfully.", "expense_id": str(new_expense.id)}

@pos_router.get("/expenses", response_model=None)
async def list_expenses(
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Returns a list of logged gym expenses. """
    stmt = select(Expense).order_by(Expense.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    expenses = res.scalars().all()
    return [
        {
            "id": str(e.id),
            "amount": float(e.amount),
            "category": e.category,
            "notes": e.notes,
            "created_at": e.created_at.strftime("%d %b %Y, %I:%M %p")
        }
        for e in expenses
    ]
