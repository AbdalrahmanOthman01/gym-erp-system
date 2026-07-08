from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.models.models_db import User, RoleEnum
from app.core.config import settings
from app.core.security import ALGORITHM
import uuid

# Dependency fetching current tokens specifically set strictly into cookie domains internally via JS POST mapping limits
async def get_token_from_cookie(request: Request):
    """ extracts auth JWT logic cleanly exclusively out of protected header cookie state loops """
    token = request.cookies.get("access_token")
    if not token:
        # Standard Unauthorized Drop mapping securely away to generic Login UX view via monolith handlers.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session Not Authenticated."
        )
    return token

async def get_current_user(
    token: str = Depends(get_token_from_cookie),
    db: AsyncSession = Depends(get_db)
) -> User:
    """ Core mapping ensuring security payload extraction ties tightly correctly resolving live targets! """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    stmt = select(User).where(User.id == uuid.UUID(user_id_str), User.is_deleted == False)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
         # Prevent users fetching views once immediately wiped / hard removed bounds correctly ensuring no persistence session access issues via cache ghost instances. 
        raise credentials_exception
        
    return user


# ===============================================
# Elite Access Control & Permissions Guards (RBAC)
# ===============================================

async def get_current_active_superuser(current_user: User = Depends(get_current_user)) -> User:
    """ System Administrator access bypass requirement. Has strict permissions! """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="You do not have enough privileges to access this control interface."
        )
    return current_user


class StrictGenderScopeValidator:
    """ 
    Enterprise logic validation injection checking target input logic dynamically parsing API boundaries securely enforcing accountant read parameters matching! 
    Because classes can carry params elegantly injected into FASTAPI route paths!
    """
    def __init__(self, allowed_genders_scope: list[str] = None):
        # Admin gets everything inherently or you declare ["male", "female"] via constraints manually where you mount dependency inside endpoint parameters limits natively securely 
        self.allowed_genders_scope = allowed_genders_scope 

    def __call__(self, target_gender: str, current_user: User = Depends(get_current_user)):
        # Master user bypass limit check naturally securing high-bound constraints seamlessly automatically correctly 
        if current_user.role == RoleEnum.SUPERADMIN:
            return True
            
        # Specific Staff scope enforcement correctly securely explicitly
        staff_allowed_target_scope = []
        if current_user.role == RoleEnum.ACCOUNTANT_M:
            staff_allowed_target_scope.append("male")
        elif current_user.role == RoleEnum.ACCOUNTANT_F:
            staff_allowed_target_scope.append("female")
            
        if target_gender not in staff_allowed_target_scope:
            raise HTTPException(
                 status_code=status.HTTP_403_FORBIDDEN,
                 detail=f"Cross Gender Access Violation Alert! Accountant ({current_user.role}) restricted operating across restricted member boundary {target_gender} natively cleanly preventing."
             )
        return True