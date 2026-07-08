import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.database import get_db
from app.core.dependencies import get_current_user
from app.models.models_db import User, RoleEnum, Product

inventory_router = APIRouter(prefix="/products", tags=["Inventory"])

# Request Schemas
class ProductCreate(BaseModel):
    name: str = Field(..., max_length=100)
    cost_price: float = Field(..., gt=0.0)
    sale_price: float = Field(..., gt=0.0)
    quantity: int = Field(0, ge=0)

class ProductUpdate(BaseModel):
    name: str = Field(..., max_length=100)
    cost_price: float = Field(..., gt=0.0)
    sale_price: float = Field(..., gt=0.0)
    quantity: int = Field(..., ge=0)

@inventory_router.get("", response_model=None)
async def list_products(
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Fetch active catalogued commodities in POS storage. """
    stmt = select(Product).where(Product.is_deleted == False)
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))
        
    stmt = stmt.order_by(Product.name.asc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    products = res.scalars().all()
    
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "cost_price": float(p.cost_price),
            "sale_price": float(p.sale_price),
            "quantity": p.quantity,
            "created_at": p.created_at.strftime("%d %b %Y")
        } for p in products
    ]

@inventory_router.post("", response_model=None)
async def create_product(
    payload: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Adds wholesale assets to system inventory list. Super Admin restricted. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Super Admins can add products.")

    # Check name uniqueness
    existing_res = await db.execute(select(Product).where(Product.name.ilike(payload.name), Product.is_deleted == False))
    if existing_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Product name already exists in the catalog.")

    product = Product(
        id=uuid.uuid4(),
        name=payload.name,
        cost_price=payload.cost_price,
        sale_price=payload.sale_price,
        quantity=payload.quantity
    )
    db.add(product)
    await db.commit()

    return {"message": "Product catalogued successfully.", "product_id": str(product.id)}

@inventory_router.put("/{product_id}", response_model=None)
async def update_product(
    product_id: str,
    payload: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Adjusts wholesale costs, shelf rates, or stock metrics. Super Admin restricted. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Super Admins can update products.")

    prod_uuid = uuid.UUID(product_id)
    res = await db.execute(select(Product).where(Product.id == prod_uuid, Product.is_deleted == False))
    product = res.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Check unique name (if changing name)
    if product.name.lower() != payload.name.lower():
        existing_res = await db.execute(select(Product).where(Product.name.ilike(payload.name), Product.is_deleted == False))
        if existing_res.scalar_one_or_none():
             raise HTTPException(status_code=400, detail="Another product is already registered with this name.")

    product.name = payload.name
    product.cost_price = payload.cost_price
    product.sale_price = payload.sale_price
    product.quantity = payload.quantity

    await db.commit()
    return {"message": "Product updated successfully."}

@inventory_router.delete("/{product_id}", response_model=None)
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """ Marks product as deleted. Super Admin restricted. """
    if current_user.role != RoleEnum.SUPERADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Super Admins can delete products.")

    prod_uuid = uuid.UUID(product_id)
    res = await db.execute(select(Product).where(Product.id == prod_uuid, Product.is_deleted == False))
    product = res.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    product.is_deleted = True
    await db.commit()

    return {"message": "Product removed from the active catalog."}
