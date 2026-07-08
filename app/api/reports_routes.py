import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.models_db import User, RoleEnum, PaymentLog, Sale, SaleItem, Product, AttendanceLog, Expense

reports_router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

@reports_router.get("/summary", response_model=None)
async def get_reports_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes analytical payloads for the SuperAdmin and Accountant Reports view.
    Enforces gender boundaries:
    - Male accountants see reports filtered by male members.
    - Female accountants see reports filtered by female members.
    - SuperAdmins see global reports.
    """
    role = current_user.role
    gender_filter = None
    if role == RoleEnum.ACCOUNTANT_M:
        gender_filter = "male"
    elif role == RoleEnum.ACCOUNTANT_F:
        gender_filter = "female"

    # Define timeframe (last 6 months for trends)
    now = datetime.now()
    six_months_ago = now - timedelta(days=180)

    # 1. HISTORICAL MONTHLY REVENUE (Last 6 Months)
    months = []
    revenue_data = []
    revenue_membership_data = []
    revenue_sales_data = []
    
    current_year = now.year
    current_month = now.month
    
    for i in range(5, -1, -1):
        m = current_month - i
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
            
        start_date = datetime(y, m, 1, 0, 0, 0)
        if m == 12:
            end_date = datetime(y + 1, 1, 1, 0, 0, 0)
        else:
            end_date = datetime(y, m + 1, 1, 0, 0, 0)
            
        month_label = start_date.strftime("%b %Y")
        months.append(month_label)
            
        # Payments in month
        p_stmt = select(func.sum(PaymentLog.amount)).where(
            PaymentLog.payment_date >= start_date,
            PaymentLog.payment_date < end_date
        )
        if gender_filter:
            p_stmt = p_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
        p_res = await db.execute(p_stmt)
        p_amount = float(p_res.scalar() or 0.0)

        # POS Sales in month
        s_stmt = select(func.sum(Sale.total_amount)).where(
            Sale.created_at >= start_date,
            Sale.created_at < end_date
        )
        if gender_filter:
            s_stmt = s_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
        s_res = await db.execute(s_stmt)
        s_amount = float(s_res.scalar() or 0.0)
        
        revenue_data.append(p_amount + s_amount)
        revenue_membership_data.append(p_amount)
        revenue_sales_data.append(s_amount)

    # 2. REVENUE BY PAYMENT METHOD
    pay_methods = {}
    p_methods_stmt = select(PaymentLog.payment_method, func.sum(PaymentLog.amount)).group_by(PaymentLog.payment_method)
    if gender_filter:
        p_methods_stmt = p_methods_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
    p_methods_res = await db.execute(p_methods_stmt)
    for row in p_methods_res.all():
        method = row[0] or "Cash"
        pay_methods[method] = pay_methods.get(method, 0.0) + float(row[1] or 0.0)

    s_methods_stmt = select(Sale.payment_method, func.sum(Sale.total_amount)).group_by(Sale.payment_method)
    if gender_filter:
        s_methods_stmt = s_methods_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
    s_methods_res = await db.execute(s_methods_stmt)
    for row in s_methods_res.all():
        method = row[0] or "Cash"
        pay_methods[method] = pay_methods.get(method, 0.0) + float(row[1] or 0.0)

    # 3. TOP SELLING PRODUCTS
    top_products = []
    prod_stmt = (
        select(Product.name, func.sum(SaleItem.quantity), func.sum(SaleItem.quantity * SaleItem.price_at_sale))
        .join(SaleItem, Product.id == SaleItem.product_id)
        .join(Sale, SaleItem.sale_id == Sale.id)
        .group_by(Product.name)
        .order_by(desc(func.sum(SaleItem.quantity)))
        .limit(5)
    )
    if gender_filter:
        prod_stmt = prod_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
        
    prod_res = await db.execute(prod_stmt)
    for row in prod_res.all():
        top_products.append({
            "name": row[0],
            "units_sold": int(row[1] or 0),
            "revenue": float(row[2] or 0.0)
        })

    # 4. ATTENDANCE TRENDS (Last 30 Days)
    attendance_labels = []
    attendance_values = []
    for i in range(29, -1, -1):
        day = now - timedelta(days=i)
        day_str = day.strftime("%d %b")
        attendance_labels.append(day_str)
        
        d_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        d_end = d_start + timedelta(days=1)
        
        att_stmt = select(func.count(AttendanceLog.id)).where(
            AttendanceLog.check_in_time >= d_start,
            AttendanceLog.check_in_time < d_end
        )
        if gender_filter:
            att_stmt = att_stmt.join(User, AttendanceLog.member_id == User.id).where(User.gender == gender_filter)
        att_res = await db.execute(att_stmt)
        attendance_values.append(att_res.scalar() or 0)

    # 5. DAILY FINANCIAL REPORT (Today)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # Subscriptions Today
    st_stmt = select(func.sum(PaymentLog.amount)).where(
        PaymentLog.payment_date >= today_start,
        PaymentLog.payment_date < today_end
    )
    if gender_filter:
        st_stmt = st_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
    st_res = await db.execute(st_stmt)
    sub_today = float(st_res.scalar() or 0.0)

    # Sales Today
    salt_stmt = select(func.sum(Sale.total_amount)).where(
        Sale.created_at >= today_start,
        Sale.created_at < today_end
    )
    if gender_filter:
        salt_stmt = salt_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
    salt_res = await db.execute(salt_stmt)
    sales_today = float(salt_res.scalar() or 0.0)

    income_today = sub_today + sales_today

    # Expenses Today
    exp_t_stmt = select(func.sum(Expense.amount)).where(
        Expense.created_at >= today_start,
        Expense.created_at < today_end
    )
    exp_t_res = await db.execute(exp_t_stmt)
    expenses_today = float(exp_t_res.scalar() or 0.0)
    net_today = income_today - expenses_today

    # 6. MONTHLY FINANCIAL REPORT (Current Calendar Month Only)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Subscriptions Month
    sm_stmt = select(func.sum(PaymentLog.amount)).where(
        PaymentLog.payment_date >= month_start,
        PaymentLog.payment_date < today_end
    )
    if gender_filter:
        sm_stmt = sm_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
    sm_res = await db.execute(sm_stmt)
    sub_month = float(sm_res.scalar() or 0.0)

    # Sales Month
    salm_stmt = select(func.sum(Sale.total_amount)).where(
        Sale.created_at >= month_start,
        Sale.created_at < today_end
    )
    if gender_filter:
        salm_stmt = salm_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
    salm_res = await db.execute(salm_stmt)
    sales_month = float(salm_res.scalar() or 0.0)

    income_month = sub_month + sales_month

    # Expenses Month
    exp_m_stmt = select(func.sum(Expense.amount)).where(
        Expense.created_at >= month_start,
        Expense.created_at < today_end
    )
    exp_m_res = await db.execute(exp_m_stmt)
    expenses_month = float(exp_m_res.scalar() or 0.0)
    net_month = income_month - expenses_month

    return {
        "months": months,
        "revenue_trend": revenue_data,
        "revenue_trend_total": revenue_data,
        "revenue_trend_membership": revenue_membership_data,
        "revenue_trend_sales": revenue_sales_data,
        "payment_methods": {
            "labels": list(pay_methods.keys()),
            "values": list(pay_methods.values())
        },
        "top_products": top_products,
        "attendance_trend": {
            "labels": attendance_labels,
            "values": attendance_values
        },
        "daily_financials": {
            "income": income_today,
            "expenses": expenses_today,
            "net": net_today
        },
        "monthly_financials": {
            "income": income_month,
            "expenses": expenses_month,
            "net": net_month
        }
    }

@reports_router.get("/history", response_model=None)
async def get_daily_history(
    date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns that day's financial summaries, the list of members
    whose membership subscriptions started on that day, and detailed expenses.
    """
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    role = current_user.role
    gender_filter = None
    if role == RoleEnum.ACCOUNTANT_M:
        gender_filter = "male"
    elif role == RoleEnum.ACCOUNTANT_F:
        gender_filter = "female"

    start_time = query_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_time = start_time + timedelta(days=1)

    # Subscriptions Income
    p_stmt = select(func.sum(PaymentLog.amount)).where(
        PaymentLog.payment_date >= start_time,
        PaymentLog.payment_date < end_time
    )
    if gender_filter:
        p_stmt = p_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
    p_res = await db.execute(p_stmt)
    sub_income = float(p_res.scalar() or 0.0)

    # POS Sales Income
    s_stmt = select(func.sum(Sale.total_amount)).where(
        Sale.created_at >= start_time,
        Sale.created_at < end_time
    )
    if gender_filter:
        s_stmt = s_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
    s_res = await db.execute(s_stmt)
    sales_income = float(s_res.scalar() or 0.0)

    total_income = sub_income + sales_income

    # Expenses
    e_stmt = select(func.sum(Expense.amount)).where(
        Expense.created_at >= start_time,
        Expense.created_at < end_time
    )
    e_res = await db.execute(e_stmt)
    total_expenses = float(e_res.scalar() or 0.0)

    net_balance = total_income - total_expenses

    # Fetch members who registered/renewed on that day
    from app.models.models_db import UserMembership, MembershipPlan
    m_stmt = select(UserMembership).where(
        UserMembership.start_date >= start_time,
        UserMembership.start_date < end_time
    ).options(selectinload(UserMembership.user))
    
    m_res = await db.execute(m_stmt)
    memberships = m_res.scalars().all()

    subscribed_members = []
    for m in memberships:
        user = m.user
        if not user or user.is_deleted:
            continue
        if gender_filter and user.gender != gender_filter:
            continue

        plan_res = await db.execute(select(MembershipPlan).where(MembershipPlan.id == m.plan_id))
        plan = plan_res.scalar_one_or_none()
        plan_name = plan.name if plan else "Unknown Plan"

        subscribed_members.append({
            "id": str(user.id),
            "full_name": user.full_name,
            "phone": user.phone,
            "gender": user.gender,
            "plan_name": plan_name,
            "paid_amount": float(m.paid_amount),
            "balance": float(m.balance)
        })

    # Fetch expenses logged on that day
    expenses_list_stmt = select(Expense).where(
        Expense.created_at >= start_time,
        Expense.created_at < end_time
    ).order_by(Expense.created_at.desc())
    expenses_list_res = await db.execute(expenses_list_stmt)
    expenses_list = expenses_list_res.scalars().all()

    logged_expenses = []
    for exp in expenses_list:
        logged_expenses.append({
            "id": str(exp.id),
            "amount": float(exp.amount),
            "category": exp.category,
            "notes": exp.notes or ""
        })

    return {
        "date": date,
        "total_income": total_income,
        "membership_income": sub_income,
        "sales_income": sales_income,
        "total_expenses": total_expenses,
        "net_balance": net_balance,
        "subscribed_members": subscribed_members,
        "expenses": logged_expenses
    }

@reports_router.get("/revenue-history", response_model=None)
async def get_revenue_history_range(
    start_date: str,
    end_date: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns daily financial reports (subscriptions, POS sales, expenses, profits)
    over a custom date range YYYY-MM-DD.
    Enforces gender boundaries:
    - Male accountants see payments & sales filtered by male members.
    - Female accountants see payments & sales filtered by female members.
    - SuperAdmins see global reports.
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="Start date must be before or equal to end date")

    if (end_dt - start_dt).days > 366:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 1 year")

    role = current_user.role
    gender_filter = None
    if role == RoleEnum.ACCOUNTANT_M:
        gender_filter = "male"
    elif role == RoleEnum.ACCOUNTANT_F:
        gender_filter = "female"

    # Grouped Payments
    p_stmt = select(
        func.date(PaymentLog.payment_date).label("date"),
        func.sum(PaymentLog.amount).label("amount")
    ).where(
        PaymentLog.payment_date >= start_dt,
        PaymentLog.payment_date < end_dt + timedelta(days=1)
    )
    if gender_filter:
        p_stmt = p_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
    p_stmt = p_stmt.group_by(func.date(PaymentLog.payment_date))
    p_res = await db.execute(p_stmt)
    payments_by_day = {}
    for row in p_res.all():
        d = row[0]
        if hasattr(d, "strftime"):
            d = d.strftime("%Y-%m-%d")
        else:
            d = str(d)
        payments_by_day[d] = float(row[1] or 0.0)

    # Grouped POS Sales
    s_stmt = select(
        func.date(Sale.created_at).label("date"),
        func.sum(Sale.total_amount).label("amount")
    ).where(
        Sale.created_at >= start_dt,
        Sale.created_at < end_dt + timedelta(days=1)
    )
    if gender_filter:
        s_stmt = s_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
    s_stmt = s_stmt.group_by(func.date(Sale.created_at))
    s_res = await db.execute(s_stmt)
    sales_by_day = {}
    for row in s_res.all():
        d = row[0]
        if hasattr(d, "strftime"):
            d = d.strftime("%Y-%m-%d")
        else:
            d = str(d)
        sales_by_day[d] = float(row[1] or 0.0)

    # Grouped Expenses
    e_stmt = select(
        func.date(Expense.created_at).label("date"),
        func.sum(Expense.amount).label("amount")
    ).where(
        Expense.created_at >= start_dt,
        Expense.created_at < end_dt + timedelta(days=1)
    ).group_by(func.date(Expense.created_at))
    e_res = await db.execute(e_stmt)
    expenses_by_day = {}
    for row in e_res.all():
        d = row[0]
        if hasattr(d, "strftime"):
            d = d.strftime("%Y-%m-%d")
        else:
            d = str(d)
        expenses_by_day[d] = float(row[1] or 0.0)

    # Generate complete list of days in the range
    history = []
    curr = start_dt
    while curr <= end_dt:
        date_str = curr.strftime("%Y-%m-%d")
        
        sub_inc = payments_by_day.get(date_str, 0.0)
        pos_inc = sales_by_day.get(date_str, 0.0)
        exp_out = expenses_by_day.get(date_str, 0.0)
        
        total_inc = sub_inc + pos_inc
        net_profit = total_inc - exp_out
        
        history.append({
            "date": date_str,
            "membership_income": sub_inc,
            "sales_income": pos_inc,
            "total_income": total_inc,
            "expenses": exp_out,
            "net_profit": net_profit
        })
        curr += timedelta(days=1)

    # Sort history descending (newest first)
    history.reverse()
    return history
