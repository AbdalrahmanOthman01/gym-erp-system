import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Float, Boolean, ForeignKey, Integer, DateTime, Numeric, Enum as SQLEnum, text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

# ==========================================
# Core System Enums (Strict Typings)
# ==========================================
class RoleEnum(str, enum.Enum):
    SUPERADMIN = "superadmin"
    ACCOUNTANT_M = "accountant_m"
    ACCOUNTANT_F = "accountant_f"
    MEMBER = "member"

class UserStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    FROZEN = "frozen"
    BLOCKED = "blocked"

class AttendanceStatusEnum(str, enum.Enum):
    SUCCESS = "success"
    AUTO_UNFROZEN = "auto_unfrozen"
    REJECT_EXPIRED = "reject_expired"
    REJECT_BLOCKED = "reject_blocked"
    REJECT_NO_SESSIONS = "reject_no_sessions"
    REJECT_DELETED = "reject_deleted"

# ==========================================
# Main System Database Models
# ==========================================

class User(Base):
    """ Central entity handling Admins, Accountants, and Gym Members. """
    __tablename__ = "users"

    # Core Identifiers
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    qr_uuid: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, unique=True, index=True)
    
    # Demographics & Data
    full_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True) # None for members
    gender: Mapped[str] = mapped_column(String(10))  # 'male' or 'female'
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Branching for multi-gym scalability later (default defaults to generic 1 via backend logic)
    branch_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=1)

    # Roles and States
    role: Mapped[RoleEnum] = mapped_column(SQLEnum(RoleEnum), default=RoleEnum.MEMBER)
    status: Mapped[UserStatusEnum] = mapped_column(SQLEnum(UserStatusEnum), default=UserStatusEnum.ACTIVE)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    join_date: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))

    # Security: Soft Delete
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Relationship Back-Populates
    memberships = relationship("UserMembership", back_populates="user", cascade="all, delete-orphan")
    measurements = relationship("BodyMeasurement", back_populates="user", cascade="all, delete-orphan")
    attendance = relationship("AttendanceLog", back_populates="member", foreign_keys="AttendanceLog.member_id")


class MembershipPlan(Base):
    """ Blueprint for all active business tiers. Set by SuperAdmins. """
    __tablename__ = "membership_plans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2))  # Stored perfectly to two decimals
    
    # Limits and Expirations
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # i.e. 30 days
    sessions_limit: Mapped[int | None] = mapped_column(Integer, nullable=True) # i.e. 10 session packet
    freeze_days: Mapped[int] = mapped_column(Integer, default=0) # Allowable pause length per term
    
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True) # Soft deprecation of old pricing
    created_at: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))

    # Relations
    user_subscriptions = relationship("UserMembership", back_populates="plan")


class UserMembership(Base):
    """ Maps an active user strictly to the conditions they paid for at point of sale. """
    __tablename__ = "user_memberships"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("membership_plans.id"))

    # Execution limits bound
    start_date: Mapped[datetime] = mapped_column(DateTime)
    end_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remaining_sessions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Financial fields for installment tracking
    paid_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)

    # Boolean indicating current focal active plan
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Navigation Properties
    user = relationship("User", back_populates="memberships")
    plan = relationship("MembershipPlan", back_populates="user_subscriptions")


class AttendanceLog(Base):
    """ 
    An immutable audit entry appended when "Scan" is clicked.
    Connects to Dashboard Analytics dynamically. 
    """
    __tablename__ = "attendance_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    member_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    scanned_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True) # Identity of the scanning accountant

    check_in_time: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))
    status: Mapped[AttendanceStatusEnum] = mapped_column(SQLEnum(AttendanceStatusEnum))

    # Back-populates for User.attendance (required to satisfy mapper configuration)
    member = relationship("User", back_populates="attendance", foreign_keys=[member_id])
    scanner = relationship("User", foreign_keys=[scanned_by])


class PaymentLog(Base):
    """ Manual overrides logic logs explicitly accounting trails per Super Admin specifications. """
    __tablename__ = "payment_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    received_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    membership_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_memberships.id"), nullable=True)

    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    payment_method: Mapped[str] = mapped_column(String(50)) # e.g. "Cash", "Visa"
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_date: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))


class BodyMeasurement(Base):
    """ Appended records building InBody charts & metrics inside Dashboards. """
    __tablename__ = "body_measurements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    date_recorded: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))
    
    weight: Mapped[float] = mapped_column(Float)       # kg
    height: Mapped[float | None] = mapped_column(Float, nullable=True) # cm
    body_fat_percentage: Mapped[float | None] = mapped_column(Float, nullable=True)
    muscle_mass: Mapped[float | None] = mapped_column(Float, nullable=True)
    bmi: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    user = relationship("User", back_populates="measurements")


class Product(Base):
    """ Wholesale merchandise catalogued by SuperAdmins. """
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    cost_price: Mapped[float] = mapped_column(Numeric(10, 2))
    sale_price: Mapped[float] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="check_product_quantity_non_negative"),
    )


class Sale(Base):
    """ Dual-ledger Point of Sale records. """
    __tablename__ = "sales"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    buyer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2))
    total_cost: Mapped[float] = mapped_column(Numeric(10, 2))
    payment_method: Mapped[str] = mapped_column(String(50)) # e.g. "Cash", "Card"
    created_at: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))

    # Relationships
    buyer = relationship("User", foreign_keys=[buyer_id])
    seller = relationship("User", foreign_keys=[seller_id])
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    """ Maps individual product checkout units. """
    __tablename__ = "sale_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sale_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sales.id"))
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    price_at_sale: Mapped[float] = mapped_column(Numeric(10, 2))
    cost_at_sale: Mapped[float] = mapped_column(Numeric(10, 2))

    sale = relationship("Sale", back_populates="items")
    product = relationship("Product")

class AuthorizedDevice(Base):
    """ Table recording authorized machine keys """
    __tablename__ = "authorized_devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    device_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))

class Expense(Base):
    """ Table recording gym expenses outflow """
    __tablename__ = "expenses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    category: Mapped[str] = mapped_column(String(100)) # e.g. "Rent", "Utilities", "Salaries", "Maintenance", "Other"
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("(CURRENT_TIMESTAMP)"))