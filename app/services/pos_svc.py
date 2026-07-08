import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from app.models.models_db import Product, Sale, SaleItem, User
from app.api.websockets import manager

class POSService:
    @staticmethod
    async def process_product_sale(
        db: AsyncSession,
        seller_id: uuid.UUID,
        buyer_id: uuid.UUID | None,
        items_payload: list[dict], # [{"product_id": "...", "quantity": int}]
        payment_method: str
    ) -> Sale:
        """
        Executes an atomic checkout session with row-level locks,
        linear stock deduction, profit ledger updates, and websocket broadcasts.
        """
        if not items_payload:
            raise HTTPException(status_code=400, detail="Cannot process an empty sale cart.")

        total_amount = 0.0
        total_cost = 0.0
        sale_items_to_create = []

        # Lock products and compute totals first
        for item in items_payload:
            prod_id_str = item["product_id"]
            qty = item["quantity"]
            if qty <= 0:
                raise HTTPException(status_code=400, detail="Quantity must be greater than zero.")
            
            try:
                prod_uuid = uuid.UUID(prod_id_str) if isinstance(prod_id_str, str) else prod_id_str
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid product ID format.")
                
            # SELECT ... FOR UPDATE enforces row locking for concurrent requests
            stmt = select(Product).where(Product.id == prod_uuid, Product.is_deleted == False).with_for_update()
            res = await db.execute(stmt)
            product = res.scalar_one_or_none()

            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Product with ID {prod_id_str} not found or deleted."
                )

            if product.quantity < qty:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for {product.name}. Requested: {qty}, Available: {product.quantity}"
                )

            # Atomic update decrement to prevent race conditions in concurrent requests
            from sqlalchemy import update
            update_stmt = (
                update(Product)
                .where(Product.id == prod_uuid, Product.quantity >= qty)
                .values(quantity=Product.quantity - qty)
            )
            update_res = await db.execute(update_stmt)
            if update_res.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Insufficient stock for {product.name} due to a concurrent transaction."
                )

            item_amount = float(product.sale_price) * qty
            item_cost = float(product.cost_price) * qty
            total_amount += item_amount
            total_cost += item_cost

            sale_items_to_create.append(
                SaleItem(
                    id=uuid.uuid4(),
                    product_id=product.id,
                    quantity=qty,
                    price_at_sale=product.sale_price,
                    cost_at_sale=product.cost_price
                )
            )

        # Create the POS Sale Dual-Ledger log
        new_sale = Sale(
            id=uuid.uuid4(),
            buyer_id=buyer_id,
            seller_id=seller_id,
            total_amount=total_amount,
            total_cost=total_cost,
            payment_method=payment_method
        )
        
        db.add(new_sale)
        
        # Link sale items
        for sale_item in sale_items_to_create:
            sale_item.sale_id = new_sale.id
            db.add(sale_item)

        await db.commit()

        # Fetch buyer name if member attached
        buyer_name = "Walk-in Guest"
        if buyer_id:
            buyer_res = await db.execute(select(User).where(User.id == buyer_id))
            buyer_user = buyer_res.scalar_one_or_none()
            if buyer_user:
                buyer_name = buyer_user.full_name

        # Broadcast Sale to Live Admin Dashboard
        await manager.broadcast({
            "event": "NEW_SALE",
            "buyer_name": buyer_name,
            "total_amount": total_amount,
            "profit": round(total_amount - total_cost, 2),
            "payment_method": payment_method,
            "timestamp": "Just Now"
        })

        return new_sale
