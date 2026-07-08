from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.models_db import User, RoleEnum
from app.services.scan_svc import AttendanceBusinessService

# We must import the Socket Manager to blast the UI updating alert
from app.api.websockets import manager

checkin_router = APIRouter()

# Validate JS input securely
class QRScanPayload(BaseModel):
    qr_uuid: str

@checkin_router.post("/attendance/scan")
async def handle_qr_scan(
    payload: QRScanPayload,
    current_admin: User = Depends(get_current_user), # Secures route!
    db: AsyncSession = Depends(get_db)
):
    """
    Called strictly by Javascript Webcam API. 
    Secured by HttpOnly JWT Cookie implicitly.
    """
    
    # 1. Basic sanity guard - don't let Gym Members scan themselves 
    if current_admin.role == RoleEnum.MEMBER:
        raise HTTPException(status_code=403, detail="Only Staff can process attendance.")
        
    # 2. Delegate everything to the Business logic
    scan_result = await AttendanceBusinessService.process_qr_scan(
        qr_uuid_str=payload.qr_uuid, 
        scanned_by_admin=current_admin.id, 
        db=db
    )
    
    # 3. WEBSOCKET BROADCAST
    # Instantly updates the "Live Feed" on every active computer in the gym without refreshing the page!
    await manager.broadcast({
        "event": "NEW_CHECKIN",
        "member_name": scan_result["member_name"],
        "timestamp": "Just Now",
        "status": scan_result["status"]
    })
    
    return scan_result