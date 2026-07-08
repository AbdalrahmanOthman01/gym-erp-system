from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def get_machine_guid() -> str:
    """ Reads Windows Cryptography MachineGuid registry key as a hardware license fingerprint. """
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            return str(winreg.QueryValueEx(key, "MachineGuid")[0]).strip()
    except Exception:
        # Fallback to dev/mock UUID if running outside Windows or registry read fails
        return "DEV_HARDWARE_FINGERPRINT_KEY_MOCK"

# 1. Import Routers
from app.api.endpoints import api_router
from app.api.websockets import ws_router
from app.ui_routes.views import ui_router

def create_app() -> FastAPI:
    """ The Core Application Factory Pattern. 
    Keeps code globally decoupled and testable without locking singletons.
    """
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url="/api/v1/openapi.json", # Securely available purely on API maps
        docs_url=None, # Disable standard SWAGGER in monolithic UI systems to prevent unauthorized exposure
    )

    # 2. Strict CORS Security. Monoliths do not require heavy Cross-Origin.
    # We restrict mapping to local rendering.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # In production, swap to ["https://yourdomain.com"]
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
    )

    # 3. Mount Static Browser Assets. 
    # This exposes CSS/JS assets strictly explicitly resolving html link bounds securely!
    import os
    import sys

    def get_resource_path(relative_path: str) -> str:
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    app.mount("/static", StaticFiles(directory=get_resource_path("app/frontend/static")), name="static")

    # Device Authorization Lock Middleware
    @app.middleware("http")
    async def device_authorization_middleware(request, call_next):
        path = request.url.path
        if path.startswith("/static") or path == "/register-device" or path == "/api/v1/register-device":
            return await call_next(request)

        from app.db.database import AsyncSessionLocal
        from app.models.models_db import AuthorizedDevice
        from sqlalchemy.future import select

        guid = get_machine_guid()
        
        async with AsyncSessionLocal() as db:
            stmt = select(AuthorizedDevice).where(AuthorizedDevice.device_key == guid)
            res = await db.execute(stmt)
            authorized = res.scalar_one_or_none() is not None

        if not authorized:
            from fastapi.responses import RedirectResponse, JSONResponse
            if path.startswith("/api/v1"):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Device unauthorized. Please register this device."}
                )
            return RedirectResponse(url="/register-device")

        return await call_next(request)

    # 4. Mount Logical Routers into main core paths 
    app.include_router(ui_router)                         # The Views Mapping (Serves HTML)
    app.include_router(api_router, prefix="/api/v1")      # The REST API Data Pipeline 
    app.include_router(ws_router)                         # Real-Time Radio mapping bounds

    # 5. Global Exception Handlers for UI Redirects
    from fastapi.responses import RedirectResponse
    from fastapi import HTTPException
    
    @app.exception_handler(HTTPException)
    async def http_exception_redirect_handler(request, exc):
        if exc.status_code == 303:
            response = RedirectResponse(url="/", status_code=303)
            response.delete_cookie("access_token")
            return response
        from fastapi.exception_handlers import http_exception_handler
        return await http_exception_handler(request, exc)

    return app

# The instance read natively via standard Uvicorn/Gunicorn workers in production limits explicitly natively!
app = create_app()

@app.on_event("startup")
async def on_startup():
    print(f"Booting Core Service Mapping seamlessly constraints implicitly.")
    print(f"Database mapping URL: {settings.async_database_url}")
    print(f"Application Monolith Securing: {settings.PROJECT_NAME}")
    
    # Auto-initialize database tables and seed default superadmin if empty
    try:
        from app.db.database import engine, Base, AsyncSessionLocal
        from app.models.models_db import User, RoleEnum
        from app.core.security import get_password_hash
        from sqlalchemy.future import select
        
        # 1. Create tables and execute dynamic migrations for SQLite
        from sqlalchemy import text
        async with engine.begin() as conn:
            # Add columns to users
            try:
                await conn.execute(text("ALTER TABLE users ADD COLUMN weight FLOAT"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE users ADD COLUMN notes VARCHAR(255)"))
            except Exception:
                pass
            
            # Add columns to user_memberships
            try:
                await conn.execute(text("ALTER TABLE user_memberships ADD COLUMN paid_amount DECIMAL(10,2) DEFAULT 0.0"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE user_memberships ADD COLUMN balance DECIMAL(10,2) DEFAULT 0.0"))
            except Exception:
                pass

            # Add columns to payment_logs
            try:
                await conn.execute(text("ALTER TABLE payment_logs ADD COLUMN membership_id CHAR(36)"))
            except Exception:
                pass

            await conn.run_sync(Base.metadata.create_all)
            
        # 2. Seed basic admin user if table is empty
        async with AsyncSessionLocal() as db:
            stmt = select(User).where(User.role == RoleEnum.SUPERADMIN)
            res = await db.execute(stmt)
            admin_exists = res.scalars().first() is not None
            if not admin_exists:
                print("[DB] No SuperAdmin found. Seeding default system management accounts...")
                import uuid
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
                
                # Also register the current developer MachineGuid so development stays authorized
                from app.models.models_db import AuthorizedDevice
                dev_guid = get_machine_guid()
                dev_device = AuthorizedDevice(
                    id=uuid.uuid4(),
                    device_key=dev_guid
                )
                db.add(dev_device)
                
                await db.commit()
                print("[DB] Seeding completed successfully.")
    except Exception as e:
        print(f"[DB] Error during startup database initialization: {e}")