from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reviews import Review as ReviewModel
from app.schemas import ReviewCreate, Review as ReviewSchema

from app.models.products import Product as ProductModel
from app.models.users import User as UserModel
from app.auth import get_current_buyer, get_current_buyer_or_admin
from app.services.rating_calculation import update_product_rating

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

@router.get("/products/{product_id}/reviews", response_model=list[ReviewSchema])
async def get_review_by_product(product_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список активных отзывов для указанного товара
    """
    # Проверка существования товара
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

    # Получение списка отзывов о товаре
    reviews = (
        await db.scalars(
            select(ReviewModel)
            .where(ReviewModel.product_id == product_id,
                   ReviewModel.is_active.is_(True))
        )
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

    # Проверка оценки (grade) на диапазон 1-5
    if not 1 <= review.grade <= 5:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Grade should be on a scale of 1–5"
        )

    # Создание нового отзыва
    db_review = ReviewModel(**review.model_dump(), user_id=current_user.id)
    db.add(db_review)
    await db.commit()
    await db.refresh(db_review)

    # Расчет среднего рейтинга товара
    await update_product_rating(review.product_id, db)

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
    update_product_rating(review.product_id, db)

    return {"message": "Review deleted"}