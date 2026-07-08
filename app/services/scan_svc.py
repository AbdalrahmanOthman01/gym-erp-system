import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from app.models.models_db import User, UserMembership, AttendanceLog, UserStatusEnum, AttendanceStatusEnum

class AttendanceBusinessService:
    
    @staticmethod
    async def process_qr_scan(qr_uuid_str: str, scanned_by_admin: uuid.UUID, db: AsyncSession) -> dict:
        """ Takes the Webcam QR string -> Evaluates User Status -> Allows/Denies Entry. """
        
        # 1. Safely Parse QR code
        try:
            target_uuid = uuid.UUID(qr_uuid_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid QR Code format.")

        # 2. Find User
        stmt = select(User).where(User.qr_uuid == target_uuid, User.is_deleted == False)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Member not found or card disabled.")

        if user.status == UserStatusEnum.BLOCKED:
            await AttendanceBusinessService._log_attendance(db, user.id, scanned_by_admin, AttendanceStatusEnum.REJECT_BLOCKED)
            raise HTTPException(status_code=403, detail="Member administratively blocked. Please contact Management.")

        # 3. Find their Active Membership Plan
        plan_stmt = select(UserMembership).where(
            UserMembership.user_id == user.id, 
            UserMembership.is_active == True
        )
        plan_result = await db.execute(plan_stmt)
        active_plan = plan_result.scalar_one_or_none()

        if not active_plan:
            await AttendanceBusinessService._log_attendance(db, user.id, scanned_by_admin, AttendanceStatusEnum.REJECT_EXPIRED)
            raise HTTPException(status_code=403, detail="No active membership plan found. Please renew subscription.")
            
        now_time = datetime.now()
        
        # 4. Check Date Expiration
        if active_plan.end_date and now_time > active_plan.end_date:
            user.status = UserStatusEnum.EXPIRED
            await AttendanceBusinessService._log_attendance(db, user.id, scanned_by_admin, AttendanceStatusEnum.REJECT_EXPIRED)
            await db.commit()
            raise HTTPException(status_code=403, detail=f"Plan expired on {active_plan.end_date.strftime('%d %b %Y')}. Please renew.")

        # 5. Check Session Limits (If it's a session-based plan)
        if active_plan.remaining_sessions is not None:
            if active_plan.remaining_sessions <= 0:
                await AttendanceBusinessService._log_attendance(db, user.id, scanned_by_admin, AttendanceStatusEnum.REJECT_NO_SESSIONS)
                raise HTTPException(status_code=403, detail="Out of sessions. Please renew session pack.")
            
            # Deduct a session explicitly on successful scan
            active_plan.remaining_sessions -= 1

        # 6. Check FROZEN logic (Our Business Rule: Auto-unfreeze on scan)
        status_flag = AttendanceStatusEnum.SUCCESS
        if user.status == UserStatusEnum.FROZEN:
            user.status = UserStatusEnum.ACTIVE
            status_flag = AttendanceStatusEnum.AUTO_UNFROZEN
            if user.frozen_at and active_plan and active_plan.end_date:
                days_frozen = (now_time - user.frozen_at).days
                days_frozen = max(1, days_frozen)
                active_plan.end_date += timedelta(days=days_frozen)
            user.frozen_at = None

        # 7. Success! Log it and Commit to Postgres
        await AttendanceBusinessService._log_attendance(db, user.id, scanned_by_admin, status_flag)
        await db.commit()

        return {
            "status": "Success",
            "member_name": user.full_name,
            "sessions_left": active_plan.remaining_sessions,
            "message": "Auto-unfrozen and entered" if status_flag == AttendanceStatusEnum.AUTO_UNFROZEN else "Successfully entered."
        }

    @staticmethod
    async def _log_attendance(db: AsyncSession, user_id: uuid.UUID, admin_id: uuid.UUID, entry_status: AttendanceStatusEnum):
        """ Internal method to append history logs strictly. """
        new_log = AttendanceLog(
            member_id=user_id,
            scanned_by=admin_id,
            status=entry_status
        )
        db.add(new_log)