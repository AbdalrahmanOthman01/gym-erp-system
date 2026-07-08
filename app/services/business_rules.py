from datetime import datetime, timedelta
from typing import Tuple

class BusinessRuleEngine:
    """ 
    Calculates gym mathematical bounds, freezes, and session lifecycles 
    without touching the Database. (Pure Functions) 
    """

    @staticmethod
    def calculate_new_expiration(start_date: datetime, duration_days: int) -> datetime:
        """ Accurately sets future plan limits based on active term lengths. """
        if not duration_days:
            return None  # Represents an infinite / session-only constraint
        return start_date + timedelta(days=duration_days)

    @staticmethod
    def calculate_freeze_return_dates(freeze_start: datetime, allocated_freeze_days: int) -> Tuple[datetime, datetime]:
        """ 
        When a Super Admin pauses a user account, this generates 
        the maximum allowed date before auto-unfreezing.
        """
        max_return_date = freeze_start + timedelta(days=allocated_freeze_days)
        return (freeze_start, max_return_date)

    @staticmethod
    def is_attendance_allowed(remaining_sessions: int, end_date: datetime, is_frozen: bool) -> tuple[bool, str]:
        """ Strict Boolean validator used before SQL queries execute """
        if is_frozen:
            return False, "ACCOUNT_FROZEN"
            
        if end_date and datetime.now() > end_date:
            return False, "EXPIRED_TIME"
            
        if remaining_sessions is not None and remaining_sessions <= 0:
            return False, "EXPIRED_SESSIONS"
            
        return True, "ALLOWED"

    @staticmethod
    def calculate_prorated_upgrade(current_plan_price: float, new_plan_price: float, days_used: int, total_duration: int) -> float:
        """ Financial arithmetic for upgrading users mid-month correctly. """
        daily_rate = current_plan_price / total_duration
        value_consumed = daily_rate * days_used
        residual_value = current_plan_price - value_consumed
        
        upgrade_cost = new_plan_price - residual_value
        return max(0.0, round(upgrade_cost, 2))