import asyncio
import uuid
import sys
import random
from datetime import datetime, timedelta

from app.db.database import AsyncSessionLocal, engine, Base
from app.models.models_db import (
    User, MembershipPlan, UserMembership, BodyMeasurement, Product,
    RoleEnum, UserStatusEnum, AttendanceLog, PaymentLog, Sale, SaleItem, AttendanceStatusEnum,
    AuthorizedDevice
)
from app.core.security import get_password_hash

async def initialize_mock_database():
    """ 
    Fills database with rich, realistic historical data over the last 6 months.
    """
    print("\n[INIT] Initiating Database Reset & Rich Seed Operations...")
    
    # Reset all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    async with AsyncSessionLocal() as db:
        # 1. MANAGEMENT ACCOUNTS
        print(">> Generating Management Users...")
        admin = User(
            id=uuid.uuid4(),
            full_name="Chief Executive Admin",
            phone="0000", 
            hashed_password=get_password_hash("password123"), 
            gender="male",
            role=RoleEnum.SUPERADMIN
        )
        
        staff_m = User(
            id=uuid.uuid4(),
            full_name="Male Floor Staff",
            phone="1111", 
            hashed_password=get_password_hash("password123"),
            gender="male",
            role=RoleEnum.ACCOUNTANT_M
        )

        staff_f = User(
            id=uuid.uuid4(),
            full_name="Female Floor Staff",
            phone="2222", 
            hashed_password=get_password_hash("password123"),
            gender="female",
            role=RoleEnum.ACCOUNTANT_F
        )
        
        db.add_all([admin, staff_m, staff_f])
        await db.commit()

        # 2. MEMBERSHIP PLANS
        print(">> Generating Membership Plan templates...")
        monthly_plan = MembershipPlan(
            id=uuid.uuid4(),
            name="Unlimited Monthly Tier",
            price=800.00,
            duration_days=30,
            freeze_days=5,
            description="Perfect for casual trainers. Includes locker access and standard equipment access."
        )
        quarterly_plan = MembershipPlan(
            id=uuid.uuid4(),
            name="Three Month Special",
            price=2000.00,
            duration_days=90,
            freeze_days=15,
            description="Our most popular plan. Save 400 EGP. Includes 1 free consultation session."
        )
        annual_plan = MembershipPlan(
            id=uuid.uuid4(),
            name="Annual VIP Membership",
            price=7000.00,
            duration_days=365,
            freeze_days=60,
            description="VIP status. 24/7 access, free nutritional plans, and guest invitations."
        )
        db.add_all([monthly_plan, quarterly_plan, annual_plan])
        await db.commit()

        # 3. PRODUCTS
        print(">> Seeding Inventory Products...")
        coca_cola = Product(
            id=uuid.uuid4(),
            name="Coca-Cola Can",
            cost_price=10.00,
            sale_price=15.00,
            quantity=50
        )
        protein_shake = Product(
            id=uuid.uuid4(),
            name="Whey Protein Shake",
            cost_price=60.00,
            sale_price=90.00,
            quantity=25
        )
        water = Product(
            id=uuid.uuid4(),
            name="Mineral Water 1L",
            cost_price=5.00,
            sale_price=10.00,
            quantity=120
        )
        db.add_all([coca_cola, protein_shake, water])
        await db.commit()

        # 4. GYM MEMBERS
        print(">> Generating 12 Athletes (Members)...")
        members_data = [
            ("Ahmed Mohamed", "01012345678", "male", UserStatusEnum.ACTIVE, monthly_plan),
            ("Sayed Abdelrahman", "01198765432", "male", UserStatusEnum.ACTIVE, quarterly_plan),
            ("Mariam Hassan", "01211112222", "female", UserStatusEnum.ACTIVE, monthly_plan),
            ("Fatma Ibrahim", "01522223333", "female", UserStatusEnum.ACTIVE, annual_plan),
            ("Mostafa Kamel", "01055556666", "male", UserStatusEnum.FROZEN, quarterly_plan),
            ("Nour El-Din", "01077778888", "male", UserStatusEnum.EXPIRED, monthly_plan),
            ("Yasmine Sabry", "01299990000", "female", UserStatusEnum.ACTIVE, monthly_plan),
            ("Hassan El-Shafei", "01133334444", "male", UserStatusEnum.BLOCKED, monthly_plan),
            ("Salma Ahmed", "01544445555", "female", UserStatusEnum.ACTIVE, quarterly_plan),
            ("Tarek Amin", "01088889999", "male", UserStatusEnum.ACTIVE, annual_plan),
            ("Rania Youssef", "01277776666", "female", UserStatusEnum.ACTIVE, monthly_plan),
            ("Sherif Nour", "01122221111", "male", UserStatusEnum.ACTIVE, quarterly_plan)
        ]

        members_list = []
        now = datetime.now()
        
        # Hardcode Ahmed Mohamed's QR UUID so scanner works with original test card
        ahmed_qr_uuid = uuid.UUID("a8f92d72-2bc0-4e2b-bb48-18e3ec8b9cd1")

        for idx, (name, phone, gender, status, plan) in enumerate(members_data):
            qr_val = ahmed_qr_uuid if name == "Ahmed Mohamed" else uuid.uuid4()
            join_offset = random.randint(10, 150) # join date in the last 150 days
            join_date = now - timedelta(days=join_offset)
            
            member = User(
                id=uuid.uuid4(),
                qr_uuid=qr_val,
                full_name=name,
                phone=phone,
                gender=gender,
                weight=random.uniform(65.0, 95.0),
                notes="Seeded member",
                status=status,
                role=RoleEnum.MEMBER,
                join_date=join_date
            )
            
            if status == UserStatusEnum.FROZEN:
                member.frozen_at = now - timedelta(days=2)

            db.add(member)
            members_list.append((member, plan, join_date))
        
        await db.commit()

        # 5. MEMBERSHIP PAYMENTS & SUBSCRIPTIONS (Last 6 Months)
        print(">> Generating Membership transactions history...")
        for member, plan, join_date in members_list:
            # Let's create payments starting from join date
            payment_date = join_date
            
            # Seed payments over time up to today
            while payment_date <= now:
                # Active/Expired Subscriptions
                sub_end = payment_date + timedelta(days=plan.duration_days)
                is_active = (payment_date <= now <= sub_end) and member.status != UserStatusEnum.EXPIRED
                
                membership = UserMembership(
                    id=uuid.uuid4(),
                    user_id=member.id,
                    plan_id=plan.id,
                    start_date=payment_date,
                    end_date=sub_end,
                    remaining_sessions=plan.sessions_limit,
                    paid_amount=plan.price,
                    balance=0.0,
                    is_active=is_active
                )
                db.add(membership)

                # Add PaymentLog linked to membership
                payment = PaymentLog(
                    id=uuid.uuid4(),
                    user_id=member.id,
                    received_by=admin.id,
                    membership_id=membership.id,
                    amount=plan.price,
                    payment_method=random.choice(["Cash", "Visa"]),
                    notes=f"Subscription renewal for: {plan.name}",
                    payment_date=payment_date
                )
                db.add(payment)
                
                # Advance date to simulate next billing cycle
                payment_date += timedelta(days=plan.duration_days + random.randint(0, 15))

            # Add one InBody measurement
            body = BodyMeasurement(
                user_id=member.id,
                weight=random.uniform(55.0, 95.0),
                height=random.uniform(155.0, 195.0),
                body_fat_percentage=random.uniform(10.0, 32.0),
                muscle_mass=random.uniform(22.0, 48.0),
                bmi=random.uniform(18.5, 30.0),
                date_recorded=join_date
            )
            db.add(body)

        await db.commit()

        # 6. PRODUCT SALES (Last 6 Months)
        print(">> Generating POS retail sales history...")
        products_list = [coca_cola, protein_shake, water]
        
        for _ in range(80):
            # Pick a date in the last 180 days
            sale_date = now - timedelta(days=random.randint(1, 180))
            buyer = random.choice([m[0] for m in members_list] + [None]) # Mix of registered members and walk-ins
            
            # Select random items
            items_to_sell = random.sample(products_list, k=random.randint(1, 2))
            total_cost = 0.0
            total_amount = 0.0
            sale_items = []
            
            for p in items_to_sell:
                qty = random.randint(1, 4)
                price = float(p.sale_price)
                cost = float(p.cost_price)
                
                total_cost += cost * qty
                total_amount += price * qty
                
                sale_items.append(SaleItem(
                    id=uuid.uuid4(),
                    product_id=p.id,
                    quantity=qty,
                    price_at_sale=price,
                    cost_at_sale=cost
                ))
            
            sale = Sale(
                id=uuid.uuid4(),
                buyer_id=buyer.id if buyer else None,
                seller_id=random.choice([staff_m.id, staff_f.id]),
                total_amount=total_amount,
                total_cost=total_cost,
                payment_method=random.choice(["Cash", "Visa", "Card"]),
                created_at=sale_date
            )
            db.add(sale)
            
            for item in sale_items:
                item.sale_id = sale.id
                db.add(item)
                
        await db.commit()

        # 7. ATTENDANCE LOGS (Last 30 Days)
        print(">> Generating daily scan logs history...")
        # Check-in hourly distribution weights (representing early morning, lunch, and evening peak hours)
        peak_hours_pool = [
            6, 7, 7, 8,                        # Morning: 6-8 AM
            9, 10, 11,                         # Off-peak
            12, 13, 13, 14,                    # Mid-day: 12-2 PM
            15, 16,                            # Off-peak
            17, 18, 18, 19, 19, 20, 20, 21, 22 # Evening: 5-10 PM
        ]

        active_members = [m[0] for m in members_list if m[0].status == UserStatusEnum.ACTIVE]
        
        for day_offset in range(30):
            day = now - timedelta(days=day_offset)
            # Generate between 5 and 15 visits per day
            daily_checkins_count = random.randint(5, 15)
            
            for _ in range(daily_checkins_count):
                member = random.choice(active_members)
                hour = random.choice(peak_hours_pool)
                minute = random.randint(0, 59)
                check_in_time = day.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                log = AttendanceLog(
                    id=uuid.uuid4(),
                    member_id=member.id,
                    scanned_by=random.choice([staff_m.id, staff_f.id]),
                    check_in_time=check_in_time,
                    status=AttendanceStatusEnum.SUCCESS
                )
                db.add(log)
                
        await db.commit()

        # 8. AUTHORIZED DEVICE (Developer Auto-registration)
        print(">> Auto-registering local developer machine...")
        from app.main import get_machine_guid
        dev_guid = get_machine_guid()
        dev_device = AuthorizedDevice(
            id=uuid.uuid4(),
            device_key=dev_guid
        )
        db.add(dev_device)
        await db.commit()

        print("-----------------------------------------------------")
        print("[OK] SUCCESS: Rich Gym Telemetry Database Deployed.")
        print(f">> Admin Login => Phone: 0000 | Pass: password123")
        print(f">> Male Staff  => Phone: 1111 | Pass: password123")
        print(f">> Female Staff => Phone: 2222 | Pass: password123")
        print(f">> Hardcoded Ahmed Mohamed's QR check-in scanner works.")
        print("-----------------------------------------------------")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(initialize_mock_database())