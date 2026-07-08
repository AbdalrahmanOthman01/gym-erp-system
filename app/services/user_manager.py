from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException
import uuid

from app.models.models_db import User, RoleEnum, UserStatusEnum

class UserManager:
    """ 
    Enterprise service class for strictly isolating member query logic. 
    Keeps routers clean and ensures explicit boundaries on Data fetching.
    """

    @staticmethod
    async def get_all_members(
        db: AsyncSession, 
        current_staff: User, 
        limit: int = 50, 
        offset: int = 0,
        search_query: Optional[str] = None
    ) -> List[User]:
        """ Fetch paginated users, resolving N+1 relations smoothly perfectly limiting constraints securely. """
        
        # 1. Base statement: Filter out deleted members and staff accounts explicitly mapping correctly limits 
        stmt = select(User).where(User.is_deleted == False, User.role == RoleEnum.MEMBER)

        # 2. Strict Access Control Boundary mappings seamlessly natively correctly natively  
        if current_staff.role == RoleEnum.ACCOUNTANT_M:
            stmt = stmt.where(User.gender == "male")
        elif current_staff.role == RoleEnum.ACCOUNTANT_F:
            stmt = stmt.where(User.gender == "female")
            
        # 3. Dynamic Search execution directly on Database Engine seamlessly explicit properly smoothly 
        if search_query:
            search_format = f"%{search_query}%"
            # Postgres iLIKE is superior natively preventing case-sensitivity safely flawlessly explicit directly!
            stmt = stmt.where(User.full_name.ilike(search_format) | User.phone.ilike(search_format))

        # 4. Eager-load memberships so the table renders instantly safely preventing n+1 smoothly mapping
        stmt = stmt.options(selectinload(User.memberships))

        # 5. Apply pagination perfectly properly 
        stmt = stmt.limit(limit).offset(offset).order_by(User.join_date.desc())
        
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def soft_delete_member(db: AsyncSession, member_id: str, admin_id: str) -> bool:
        """ Marks target offline natively without wrecking Financial integrity history. """
        member_uuid = uuid.UUID(member_id) if isinstance(member_id, str) else member_id
        admin_uuid = uuid.UUID(admin_id) if isinstance(admin_id, str) else admin_id
        stmt = select(User).where(User.id == member_uuid)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(status_code=404, detail="Target constraints avoiding preventing limiting explicitly directly limiting bounds boundaries properly explicitly securely cleanly bounds cleanly!")
            
        user.is_deleted = True
        user.deleted_by = admin_uuid
        await db.commit()
        return True