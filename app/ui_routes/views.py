from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt
import uuid
from typing import Optional

from app.db.database import get_db
from app.models.models_db import User, RoleEnum, UserMembership, MembershipPlan
from app.core.config import settings
from app.core.security import ALGORITHM

ui_router = APIRouter()

# Tell FastAPI exactly where the raw HTML files live
import os
import sys

def get_resource_path(relative_path: str) -> str:
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

templates = Jinja2Templates(directory=get_resource_path("app/frontend/templates"))

async def get_current_user_ui(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """ Helper to fetch user details in UI views for page rendering. """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=303, detail="Redirecting to Login", headers={"Location": "/"})
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=303, detail="Redirecting to Login", headers={"Location": "/"})
    except Exception:
         raise HTTPException(status_code=303, detail="Redirecting to Login", headers={"Location": "/"})

    stmt = select(User).where(User.id == uuid.UUID(user_id_str), User.is_deleted == False)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
         raise HTTPException(status_code=303, detail="Redirecting to Login", headers={"Location": "/"})
    return user


@ui_router.get("/", response_class=HTMLResponse)
async def serve_base_landing(request: Request):
    """ The Login Page / Application root. Redirects instantly if already logged in. """
    if "access_token" in request.cookies:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html")


@ui_router.get("/register-device", response_class=HTMLResponse)
async def serve_register_device(request: Request):
    """ Serves the device registration security screen. """
    from app.main import get_machine_guid
    guid = get_machine_guid()
    return templates.TemplateResponse(
        request, 
        "auth/register_device.html", 
        {"device_guid": guid}
    )



@ui_router.get("/dashboard", response_class=HTMLResponse)
async def render_live_dashboard(
    request: Request,
    member_id: Optional[str] = None,
    current_user: User = Depends(get_current_user_ui),
    db: AsyncSession = Depends(get_db)
):
    """
    Dual-mode view rendering:
    - Default: Global gym-wide telemetry statistics dashboard.
    - If member_id supplied: Single member analytics detail profile (respecting gender scope).
    """
    member_data = None
    
    if member_id:
        member_uuid = uuid.UUID(member_id)
        stmt = select(User).where(User.id == member_uuid, User.is_deleted == False)
        res = await db.execute(stmt)
        member_data = res.scalar_one_or_none()
        
        if not member_data:
             raise HTTPException(status_code=404, detail="Gym member not found.")

        # Strict Gender Privacy Boundary Validation
        if current_user.role != RoleEnum.SUPERADMIN:
            allowed_gender = "male" if current_user.role == RoleEnum.ACCOUNTANT_M else "female"
            if member_data.gender != allowed_gender:
                raise HTTPException(
                    status_code=403,
                    detail="Cross Gender Access Violation! Accountant is restricted from fetching opposite gender profile details."
                )

    return templates.TemplateResponse(
        request, "pages/dashboard.html",
        {
            "page_title": "Member Analytics Profile" if member_id else "ERP System HQ",
            "current_user": current_user,
            "member_id": member_id,
            "member_data": member_data
        }
    )


@ui_router.get("/scan", response_class=HTMLResponse)
async def render_camera_qr_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ Isolated camera scanning terminal UI. """
    return templates.TemplateResponse(
        request, "scanner/scan.html",
        {"page_title": "Attendance Console", "current_user": current_user}
    )
    
@ui_router.get("/members", response_class=HTMLResponse)
async def render_members_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view managing all members in a data table. """
    return templates.TemplateResponse(
        request, "pages/members.html",
        {"page_title": "Member Management", "current_user": current_user}
    )

@ui_router.get("/members/new", response_class=HTMLResponse)
async def render_new_member_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view to register a new member. """
    return templates.TemplateResponse(
        request, "pages/members_new.html",
        {"page_title": "Add New Member", "current_user": current_user}
    )

@ui_router.get("/attendance", response_class=HTMLResponse)
async def render_attendance_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ Alias for /scan to match sidebar links. """
    return templates.TemplateResponse(
        request, "scanner/scan.html",
        {"page_title": "Attendance Console", "current_user": current_user}
    )

@ui_router.get("/plans", response_class=HTMLResponse)
async def render_plans_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view to configure plans. """
    if current_user.role != RoleEnum.SUPERADMIN:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request, "pages/membership.html",
        {"page_title": "Configure Plans", "current_user": current_user}
    )

@ui_router.get("/payments", response_class=HTMLResponse)
async def render_payments_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view for finance ledger. """
    return templates.TemplateResponse(
        request, "pages/payment.html",
        {"page_title": "Log Revenue", "current_user": current_user}
    )

@ui_router.get("/inventory", response_class=HTMLResponse)
async def render_inventory_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view for managing catalogued products (Super Admin only). """
    if current_user.role != RoleEnum.SUPERADMIN:
         raise HTTPException(status_code=403, detail="You do not have enough privileges to access the inventory catalog.")
    return templates.TemplateResponse(
        request, "pages/inventory.html",
        {"page_title": "Inventory Management", "current_user": current_user}
    )

@ui_router.get("/pos", response_class=HTMLResponse)
async def render_pos_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view for checkout POS cash register. """
    return templates.TemplateResponse(
        request, "pages/pos.html",
        {"page_title": "Point of Sale Cashier", "current_user": current_user}
    )

@ui_router.get("/settings", response_class=HTMLResponse)
async def render_settings_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view for system settings. """
    if current_user.role != RoleEnum.SUPERADMIN:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request, "pages/settings.html",
        {"page_title": "Platform Settings", "current_user": current_user}
    )

@ui_router.get("/staff", response_class=HTMLResponse)
async def render_staff_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view for staff user management (SuperAdmin only). """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=403, detail="You do not have enough privileges to access staff management.")
    return templates.TemplateResponse(
        request, "pages/staff.html",
        {"page_title": "Staff Management", "current_user": current_user}
    )

@ui_router.get("/reports", response_class=HTMLResponse)
async def render_reports_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view for viewing revenue, product sales, and check-in reports. """
    if current_user.role != RoleEnum.SUPERADMIN:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request, "pages/reports.html",
        {"page_title": "Reports & Analytics", "current_user": current_user}
    )

@ui_router.get("/notifications", response_class=HTMLResponse)
async def render_notifications_view(request: Request, current_user: User = Depends(get_current_user_ui)):
    """ UI view for displaying active operational system alerts. """
    return templates.TemplateResponse(
        request, "pages/notifications.html",
        {"page_title": "Notifications & Alerts", "current_user": current_user}
    )