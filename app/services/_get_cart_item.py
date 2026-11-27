from fastapi import Depends, HTTPException, status

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart_items import CartItem as CartItemModel

async def _get_cart_item(
        user_id: int,
        product_id: int,
        db: AsyncSession
) -> CartItemModel | None:
    result = await db.scalars(
        select(CartItemModel)
        .options(selectinload(CartItemModel.product))
        .where(
            CartItemModel.user_id == user_id,
            CartItemModel.product_id == product_id
        )
    )
    return result.first()