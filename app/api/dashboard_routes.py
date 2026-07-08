import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, distinct

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.models_db import User, RoleEnum, UserStatusEnum, AttendanceLog, PaymentLog, Sale, Product, UserMembership

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@dashboard_router.get("/stats", response_model=None)
async def get_dashboard_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Assembles complete data package for real-time widgets and charts.
    Filters demographics and attendance to respect gender scopes for Accountant roles.
    """
    role = current_user.role
    gender_filter = None
    if role == RoleEnum.ACCOUNTANT_M:
        gender_filter = "male"
    elif role == RoleEnum.ACCOUNTANT_F:
        gender_filter = "female"

    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # 1. Active Members count
    m_stmt = select(func.count(User.id)).where(User.role == RoleEnum.MEMBER, User.is_deleted == False)
    if gender_filter:
        m_stmt = m_stmt.where(User.gender == gender_filter)
    m_res = await db.execute(m_stmt)
    total_active_members = m_res.scalar() or 0

    # 2. Check-ins Today
    c_stmt = select(func.count(AttendanceLog.id)).where(AttendanceLog.check_in_time >= today_start)
    if gender_filter:
        c_stmt = c_stmt.join(User, AttendanceLog.member_id == User.id).where(User.gender == gender_filter)
    c_res = await db.execute(c_stmt)
    checkins_today = c_res.scalar() or 0

    # 3. Revenue calculations
    # Payments Today
    pay_stmt = select(func.sum(PaymentLog.amount)).where(PaymentLog.payment_date >= today_start)
    if gender_filter:
        pay_stmt = pay_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
    pay_res = await db.execute(pay_stmt)
    pay_today = float(pay_res.scalar() or 0.0)

    # Sales Today
    sale_stmt = select(func.sum(Sale.total_amount)).where(Sale.created_at >= today_start)
    if gender_filter:
        sale_stmt = sale_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
    sale_res = await db.execute(sale_stmt)
    sale_today = float(sale_res.scalar() or 0.0)

    revenue_today = pay_today + sale_today

    # 4. Low stock items (SuperAdmin sees inventory; accountants get general notification or 0 if hidden)
    prod_stmt = select(func.count(Product.id)).where(Product.quantity <= 5, Product.is_deleted == False)
    prod_res = await db.execute(prod_stmt)
    low_stock_count = prod_res.scalar() or 0

    # 5. Last 14 days checkins for main Bar Chart
    days_labels = []
    days_values = []
    for i in range(13, -1, -1):
        day = datetime.now() - timedelta(days=i)
        day_str = day.strftime("%d %b")
        days_labels.append(day_str)
        
        d_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        d_end = d_start + timedelta(days=1)
        
        day_stmt = select(func.count(AttendanceLog.id)).where(
            AttendanceLog.check_in_time >= d_start,
            AttendanceLog.check_in_time < d_end
        )
        if gender_filter:
            day_stmt = day_stmt.join(User, AttendanceLog.member_id == User.id).where(User.gender == gender_filter)
        day_res = await db.execute(day_stmt)
        days_values.append(day_res.scalar() or 0)

    # 6. Peak Hours Analysis (6 AM, 9 AM, 12 PM, 3 PM, 6 PM, 9 PM)
    peak_labels = ["6 AM", "9 AM", "12 PM", "3 PM", "6 PM", "9 PM"]
    peak_values = [0] * len(peak_labels)
    # We query all check-ins for peak evaluation
    peak_stmt = select(AttendanceLog.check_in_time)
    if gender_filter:
        peak_stmt = peak_stmt.join(User, AttendanceLog.member_id == User.id).where(User.gender == gender_filter)
    peak_res = await db.execute(peak_stmt)
    checkin_times = peak_res.scalars().all()
    for t in checkin_times:
        hour = t.hour
        if 5 <= hour < 8:
            peak_values[0] += 1
        elif 8 <= hour < 11:
            peak_values[1] += 1
        elif 11 <= hour < 14:
            peak_values[2] += 1
        elif 14 <= hour < 17:
            peak_values[3] += 1
        elif 17 <= hour < 20:
            peak_values[4] += 1
        elif 20 <= hour < 23:
            peak_values[5] += 1

    # 7. Visit Frequency (Doughnut chart)
    # Categorizes members by check-in counts: '1 time', '2-3 times', '4+ times'
    freq_stmt = select(AttendanceLog.member_id, func.count(AttendanceLog.id)).group_by(AttendanceLog.member_id)
    if gender_filter:
        freq_stmt = freq_stmt.join(User, AttendanceLog.member_id == User.id).where(User.gender == gender_filter)
    freq_res = await db.execute(freq_stmt)
    records = freq_res.all()
    
    visit_freq = {"1 time": 0, "2-3 times": 0, "4+ times": 0}
    for r in records:
        count = r[1]
        if count == 1:
            visit_freq["1 time"] += 1
        elif 2 <= count <= 3:
            visit_freq["2-3 times"] += 1
        else:
            visit_freq["4+ times"] += 1
    
    # 8. Plan Usage Ratio
    plan_stmt = select(UserMembership.is_active, func.count(UserMembership.id)).group_by(UserMembership.is_active)
    if gender_filter:
         plan_stmt = plan_stmt.join(User, UserMembership.user_id == User.id).where(User.gender == gender_filter)
    plan_res = await db.execute(plan_stmt)
    plan_records = plan_res.all()
    plan_usage = {"Active": 0, "Expired": 0}
    for r in plan_records:
        if r[0] is True:
            plan_usage["Active"] = r[1]
        else:
            plan_usage["Expired"] = r[1]

    # 9. Demographic Split
    demo_stmt = select(User.gender, func.count(User.id)).where(User.role == RoleEnum.MEMBER, User.is_deleted == False).group_by(User.gender)
    demo_res = await db.execute(demo_stmt)
    demo_records = demo_res.all()
    demographics = {"Male": 0, "Female": 0}
    for r in demo_records:
        if r[0] == "male":
            demographics["Male"] = r[1]
        elif r[0] == "female":
            demographics["Female"] = r[1]

    # 10. Live Feed (unified activity logs from last 10 entries)
    feed_stmt = select(AttendanceLog).order_by(AttendanceLog.check_in_time.desc()).limit(10)
    feed_res = await db.execute(feed_stmt)
    logs = feed_res.scalars().all()
    
    feed = []
    for log in logs:
        # Fetch member details
        m_detail_res = await db.execute(select(User).where(User.id == log.member_id))
        member = m_detail_res.scalar_one_or_none()
        if not member:
            continue
            
        if gender_filter and member.gender != gender_filter:
            continue

        feed.append({
            "type": "checkin",
            "title": f"Check-in: {member.full_name}",
            "description": f"Status: {log.status.value.replace('_', ' ').title()}",
            "timestamp": log.check_in_time.strftime("%I:%M %p")
        })

    # Fetch recent sales for the feed
    sales_feed_stmt = select(Sale).order_by(Sale.created_at.desc()).limit(5)
    sales_feed_res = await db.execute(sales_feed_stmt)
    recent_sales = sales_feed_res.scalars().all()
    for sale in recent_sales:
        buyer_name = "Walk-in Guest"
        if sale.buyer_id:
            b_detail_res = await db.execute(select(User).where(User.id == sale.buyer_id))
            b_user = b_detail_res.scalar_one_or_none()
            if b_user:
                if gender_filter and b_user.gender != gender_filter:
                    continue
                buyer_name = b_user.full_name
        
        feed.append({
            "type": "sale",
            "title": f"POS Sale: {buyer_name}",
            "description": f"Spent: {float(sale.total_amount)} EGP ({sale.payment_method})",
            "timestamp": sale.created_at.strftime("%I:%M %p")
        })
    
    # Sort unified feed by timestamp
    feed.sort(key=lambda x: x["timestamp"], reverse=True)

    # 10.1 Recent Revenue History (last 10 unified logs)
    # Fetch last 10 PaymentLog entries
    p_log_stmt = select(PaymentLog).order_by(PaymentLog.payment_date.desc()).limit(10)
    if gender_filter:
        p_log_stmt = p_log_stmt.join(User, PaymentLog.user_id == User.id).where(User.gender == gender_filter)
    p_log_res = await db.execute(p_log_stmt)
    payment_logs = p_log_res.scalars().all()

    # Fetch last 10 Sale entries
    s_log_stmt = select(Sale).order_by(Sale.created_at.desc()).limit(10).options(selectinload(Sale.buyer), selectinload(Sale.seller))
    if gender_filter:
        s_log_stmt = s_log_stmt.join(User, Sale.buyer_id == User.id).where(User.gender == gender_filter)
    s_log_res = await db.execute(s_log_stmt)
    sales = s_log_res.scalars().all()

    recent_revenue = []

    # Map manual payments
    for log in payment_logs:
        member_res = await db.execute(select(User).where(User.id == log.user_id))
        member = member_res.scalar_one_or_none()
        
        staff_res = await db.execute(select(User).where(User.id == log.received_by))
        staff = staff_res.scalar_one_or_none()
        
        recent_revenue.append({
            "id": str(log.id),
            "type": "Membership Payment",
            "member_name": member.full_name if member else "Unknown Member",
            "phone": member.phone if member else "N/A",
            "amount": float(log.amount),
            "payment_method": log.payment_method,
            "processed_by": staff.full_name if staff else "Staff",
            "timestamp_raw": log.payment_date,
            "timestamp": log.payment_date.strftime("%I:%M %p")
        })

    # Map POS sales
    for sale in sales:
        recent_revenue.append({
            "id": str(sale.id),
            "type": "Merchandise POS",
            "member_name": sale.buyer.full_name if sale.buyer else "Walk-in Guest",
            "phone": sale.buyer.phone if sale.buyer else "N/A",
            "amount": float(sale.total_amount),
            "payment_method": sale.payment_method,
            "processed_by": sale.seller.full_name if sale.seller else "Staff",
            "timestamp_raw": sale.created_at,
            "timestamp": sale.created_at.strftime("%I:%M %p")
        })

    # Sort unified recent revenue chronologically (newest first)
    recent_revenue.sort(key=lambda x: x["timestamp_raw"], reverse=True)
    recent_revenue = recent_revenue[:10]
    
    # Strip timestamp_raw
    for r in recent_revenue:
        r.pop("timestamp_raw", None)

    return {
        "active_members": total_active_members,
        "checkins_today": checkins_today,
        "revenue_today": revenue_today,
        "revenue_today_membership": pay_today,
        "revenue_today_sales": sale_today,
        "low_stock_count": low_stock_count,
        "recent_revenue": recent_revenue,
        "charts": {
            "bar_checkins": {
                "labels": days_labels,
                "values": days_values
            },
            "peak_hours": {
                "labels": peak_labels,
                "values": peak_values
            },
            "visit_frequency": {
                "labels": list(visit_freq.keys()),
                "values": list(visit_freq.values())
            },
            "plan_usage": {
                "labels": list(plan_usage.keys()),
                "values": list(plan_usage.values())
            },
            "demographics": {
                "labels": list(demographics.keys()),
                "values": list(demographics.values())
            }
        },
        "live_feed": feed[:10]
    }
