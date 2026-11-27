from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reviews import Review as ReviewModel
from app.schemas import ReviewCreate, Review as ReviewSchema

from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.auth import get_current_buyer, get_current_buyer_or_admin
from app.services._rating_calculation import _update_product_rating

from app.db_depends import get_async_db

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"]
)

@router.get("/", response_model=list[ReviewSchema])
async def get_all_reviews(db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список всех активных отзывов о товарах
    """
    reviews = (
        await db.scalars(select(ReviewModel).where(ReviewModel.is_active.is_(True)))
    ).all()

    return reviews

@router.post("/", response_model=ReviewSchema, status_code=status.HTTP_201_CREATED)
async def create_review(
    review: ReviewCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_buyer)
):
    """
    Создаёт новый отзыв для указанного товара.
    После добавления отзыва пересчитывает средний рейтинг товара
    """
    # Проверка существования товара
    product = (
        await db.scalars(
            select(ProductModel)
            .where(ProductModel.id == review.product_id,
                   ProductModel.is_active.is_(True))
        )
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product not found or inactive"
        )

    # Проверка того, что пользователь не оставлял отзыв ранее
    # Для избежания накрутки отзывов
    review = (
        await db.scalars(
            select(ReviewModel)
            .where(ReviewModel.is_active.is_(True),
                   ReviewModel.user_id == current_user.id)
        )
    ).first()
    if review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already write a review for this product"
        )

    # Создание нового отзыва
    db_review = ReviewModel(**review.model_dump(), user_id=current_user.id)
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)

    # Расчет среднего рейтинга товара
    await _update_product_rating(review.product_id, db)

    # Возврат отзыва
    return db_review

@router.delete("/{review_id}")
async def delete_review(
    review_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_buyer_or_admin)
):
    """
    Выполняет мягкое удаление отзыва по review_id, устанавливая is_active = False.
    После удаления пересчитывает рейтинг товара на основе оставшихся активных отзывов
    """
    # Проверка существования отзыва
    review = (
        await db.scalars(
            select(ReviewModel)
            .where(ReviewModel.id == review_id,
                   ReviewModel.is_active.is_(True))
        )
    ).first()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or inactive"
        )

    # Проверка принадлежности отзыва к автору или что пользователь - админ
    if review.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews"
        )

    # Логическое удаление отзыва
    await db.execute(
        update(ReviewModel)
        .where(ReviewModel.id == review_id)
        .values(is_active=False)
    )
    await db.commit()
    await db.refresh(review)

    # Расчет среднего рейтинга товара
    _update_product_rating(review.product_id, db)

    return {"message": "Review deleted"}