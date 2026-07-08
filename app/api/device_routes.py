import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.models.models_db import AuthorizedDevice

device_router = APIRouter(prefix="/register-device", tags=["Device Licensing"])

# Security lock password configuration
LICENSING_PASSWORD = "Starkothman1234567890)(*&^%$#@!abdalrahman"

class DeviceRegistrationPayload(BaseModel):
    password: str = Field(..., description="Authorization password to register the machine")

@device_router.post("", response_model=None)
async def register_device(
    payload: DeviceRegistrationPayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Registers the current device's Windows Machine GUID if the authorization password matches.
    """
    if payload.password != LICENSING_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect authorization password."
        )

    # Resolve active windows key fingerprint
    from app.main import get_machine_guid
    guid = get_machine_guid()

    # Verify if already registered
    stmt = select(AuthorizedDevice).where(AuthorizedDevice.device_key == guid)
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if not existing:
        new_device = AuthorizedDevice(
            id=uuid.uuid4(),
            device_key=guid
        )
        db.add(new_device)
        await db.commit()

    return {"message": "Device registered successfully! Access is unlocked."}
