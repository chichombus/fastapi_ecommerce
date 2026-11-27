from fastapi import Depends, HTTPException, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.products import Product as ProductModel


async def _ensure_product_available(product_id: int, db: AsyncSession) -> None:
    product = (
        await db.scalars(
            select(ProductModel)
            .where(ProductModel.id == product_id,
                   ProductModel.is_active.is_(True))
        )
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or inactive"
        )