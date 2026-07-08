from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import uuid

from app.models.models_db import PaymentLog

class FinanceService:
    """ Operations extracting financial aggregate analytics for dashboards. """

    @staticmethod
    async def get_today_revenue(db: AsyncSession) -> float:
        """ Calculates sum of physical POS logs stored today. """
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        stmt = select(func.sum(PaymentLog.amount)).where(
            PaymentLog.payment_date >= today_start
        )
        result = await db.execute(stmt)
        total = result.scalar()
        
        return float(total) if total else 0.00

    @staticmethod
    async def process_manual_payment(db: AsyncSession, member_id: str, admin_id: str, amount: float, method: str, notes: str) -> bool:
        """ Logs manual physical local desk transactions securely. """
        member_uuid = uuid.UUID(member_id) if isinstance(member_id, str) else member_id
        admin_uuid = uuid.UUID(admin_id) if isinstance(admin_id, str) else admin_id
        new_payment = PaymentLog(
            user_id=member_uuid,
            received_by=admin_uuid,
            amount=amount,
            payment_method=method, # i.e., "Cash", "Visa"
            notes=notes
        )
        db.add(new_payment)
        await db.commit()
        return True