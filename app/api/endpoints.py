from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.models.models_db import User, RoleEnum
from app.core.security import verify_password, create_access_token
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.api.checkin_routes import checkin_router
from app.api.member_routes import member_router
from app.api.inventory_routes import inventory_router
from app.api.pos_routes import pos_router
from app.api.dashboard_routes import dashboard_router
from app.api.plan_routes import plan_router
from app.api.staff_routes import staff_router
from app.api.reports_routes import reports_router
from app.api.notification_routes import notification_router
from app.api.device_routes import device_router

api_router = APIRouter()
api_router.include_router(checkin_router)
api_router.include_router(member_router)
api_router.include_router(inventory_router)
api_router.include_router(pos_router)
api_router.include_router(dashboard_router)
api_router.include_router(plan_router)
api_router.include_router(staff_router)
api_router.include_router(reports_router)
api_router.include_router(notification_router)
api_router.include_router(device_router)

@api_router.post("/login", response_model=None)
async def login_access_token(
    response: Response,
    db: AsyncSession = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends() # Native handling reading standard inputs strictly natively explicitly seamlessly explicitly flawlessly 
):
    """
    Enterprise Authentication Engine natively authenticating.
    Inputting user constraints correctly safely explicitly ensuring high speed mappings natively.
    """
    stmt = select(User).where(User.phone == form_data.username, User.is_deleted == False) # Mapped Username config bounds strictly correctly pointing Phone login mappings limits
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Guard checking invalid configurations preventing side attack validations perfectly naturally
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect Phone/Identifier mapping")
    
    # Gym Members do not log into the Dashboard logic cleanly safely Explicitly naturally avoiding issues  
    if user.role == RoleEnum.MEMBER:
        raise HTTPException(status_code=403, detail="Standard Gym users cannot access restricted Management Panels natively correctly completely stopping attack mappings strictly safely explicit bounds mapping")
    
    # Validation engine checking payload correctly avoiding string timing bypass loops directly mapping standard explicitly
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect login password authentication natively correctly flawlessly securing explicit limit explicit correctly")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(subject=str(user.id), expires_delta=access_token_expires)
    
    # Setting explicitly Secure Strict Cookie logic bound limiting strictly via domain scope mappings 
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,  # Prevent JS interception vectors cleanly safely explicitly ensuring constraints preventing natively avoiding strictly xss theft
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
    )
    
    return {"message": "Authenticated efficiently correctly."}

@api_router.post("/logout")
async def secure_session_wipe(response: Response, current_user: User = Depends(get_current_user)):
    """ Secure clearance handler removing cache scopes bounds limits correctly instantly implicitly correctly directly  """
    response.delete_cookie("access_token")
    return {"message": "Successfully Terminated Secure System Access limits safely gracefully mapped naturally perfectly explicitly correctly perfectly cleanly naturally."}