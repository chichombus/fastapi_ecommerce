from fastapi import Depends

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reviews import Review as ReviewModel
from app.models.products import Product as ProductModel

from app.db_depends import get_async_db

async def update_product_rating(product_id: int, db: AsyncSession = Depends(get_async_db)):
    result = await db.execute(
        select(func.avg(ReviewModel.grade))
        .where(ReviewModel.product_id == product_id,
               ReviewModel.is_active.is_(True))
    )
    avg_rating = result.scalar() or 0.0
    await db.execute(
            update(ProductModel)
            .where(ProductModel.id == product_id)
            .values(rating=avg_rating)
        )
    await db.commit()