"""Dynamic Automated Counting Engine for Industrial Goods (Boxes, Cement, Iron Rods)"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import Product, MaterialMovementLedger, MaterialInventoryBalance

class AutomatedCountingEngine:
    @classmethod
    async def process_vision_count(
        cls, 
        session: AsyncSession, 
        camera_id: str, 
        vision_counts: Dict[int, int] # {vision_class_id: count}
    ) -> Dict[str, Any]:
        """
        Dynamically maps YOLOX bounding box counts to Database Products without hardcoding.
        Updates the Inventory Balance and logs the event in the Movement Ledger.
        """
        results = []
        
        for vision_class_id, count in vision_counts.items():
            if count <= 0:
                continue
                
            # Dynamically resolve Product by Vision Class ID
            stmt = select(Product).where(Product.vision_class_id == vision_class_id)
            res = await session.execute(stmt)
            product = res.scalars().first()
            
            if not product:
                # If no product matches the class, we skip (or log anomaly)
                continue
                
            # 1. Update Inventory Balance
            balance_stmt = select(MaterialInventoryBalance).where(
                MaterialInventoryBalance.product_id == product.product_id
            )
            balance_res = await session.execute(balance_stmt)
            balance_record = balance_res.scalars().first()
            
            if not balance_record:
                balance_record = MaterialInventoryBalance(
                    product_id=product.product_id,
                    available_qty=0
                )
                session.add(balance_record)
            
            balance_record.available_qty += count
            
            # 2. Append immutable ledger row (Double-Entry principles)
            ledger_entry = MaterialMovementLedger(
                product_id=product.product_id,
                movement_type="IN_VISION_COUNT",
                qty_change=count,
                reference_source=f"CAMERA_{camera_id}",
                notes=f"Automated Count: {product.name}"
            )
            session.add(ledger_entry)
            
            results.append({
                "product_id": product.product_id,
                "sku": product.sku_code,
                "name": product.name,
                "category": product.category,
                "qty_counted": count
            })
            
        await session.commit()
        return {"status": "success", "tallied_items": results}
        
    @classmethod
    async def manual_adjustment(
        cls,
        session: AsyncSession,
        product_id: str,
        qty_adjustment: int,
        operator_id: str,
        reason: str
    ) -> Dict[str, Any]:
        """
        Allows operators to adjust discrepancies. Preserves original ML count, merely appends correction.
        """
        # Ensure Product exists
        stmt = select(Product).where(Product.product_id == product_id)
        res = await session.execute(stmt)
        product = res.scalars().first()
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        # Update Inventory Balance
        balance_stmt = select(MaterialInventoryBalance).where(
            MaterialInventoryBalance.product_id == product.product_id
        )
        balance_res = await session.execute(balance_stmt)
        balance_record = balance_res.scalars().first()
        
        if not balance_record:
            balance_record = MaterialInventoryBalance(
                product_id=product.product_id,
                available_qty=0
            )
            session.add(balance_record)
            
        balance_record.available_qty += qty_adjustment
        
        # Append correction row
        ledger_entry = MaterialMovementLedger(
            product_id=product.product_id,
            movement_type="MANUAL_CORRECTION",
            qty_change=qty_adjustment,
            reference_source=f"OPERATOR_{operator_id}",
            notes=reason
        )
        session.add(ledger_entry)
        await session.commit()
        
        return {
            "status": "adjusted", 
            "product": product.name, 
            "adjustment": qty_adjustment,
            "new_balance": balance_record.available_qty
        }
