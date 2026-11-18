from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, update, func, desc
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.products import Product as ProductModel
from app.models.categories import Category as CategoryModel
from app.models.users import User as UserModel
from app.auth import get_current_seller
from app.schemas import ProductCreate, Product as ProductSchema, ProductList
from app.db_depends import get_db, get_async_db

# Создаем маршрутизаторв для товаров
router = APIRouter(
    prefix="/products",
    tags=["products"]
)


@router.get("/", response_model=ProductList)
async def get_all_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Возвращает список всех товаров
    """
    total_stmt = select(func.count()).select_from(ProductModel).where(ProductModel.is_active.is_(True))
    total = await db.scalar(total_stmt) or 0

    items = (
        await db.scalars(
            select(ProductModel)
            .where(ProductModel.is_active.is_(True))
            .order_by(ProductModel.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@router.get("/category/{category_id}", response_model=list[ProductSchema])
async def get_products_by_category(category_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает список товаров в указанной категории по ее ID
    """
    # Проверка существования категории
    category = (
        await db.scalars(select(CategoryModel)
                         .where(CategoryModel.id == category_id,
                                CategoryModel.is_active.is_(True)))
    ).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found or inactive")

    # Получение списка товаров по категории
    products = (
        await db.scalars(select(ProductModel)
                         .where(ProductModel.category_id == category_id,
                                ProductModel.is_active.is_(True)))
    ).all()
    return products

@router.get("/{product_id}", response_model=ProductSchema)
async def get_product(product_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Возвращает детальную информацию о товаре по его ID
    """
    # Получение товара по ID
    product = (
        await db.scalars(select(ProductModel)
                         .where(ProductModel.id == product_id,
                                ProductModel.is_active.is_(True)))
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    # Проверка существования категории
    category = (
        await db.scalars(select(CategoryModel)
                         .where(CategoryModel.id == product.category_id,
                                CategoryModel.is_active.is_(True)))
    ).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    return product

@router.post("/", response_model=ProductSchema, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_seller)
):
    """
    Создает новый товар, привязанный к текущему продавцу (толькео для 'seller')
    """
    # Проверка существования категории
    category = (await db.scalars(select(CategoryModel).where(CategoryModel.id == product.category_id,
                                                             CategoryModel.is_active.is_(True)))).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    # Создание нового товара
    db_product = ProductModel(**product.model_dump(), seller_id=current_user.id)
    db.add(db_product)
    await db.commit()
    await db.refresh(db_product)
    return db_product

@router.put("/{product_id}", response_model=ProductSchema)
async def update_product(
    product_id: int,
    payload: ProductCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_seller)
):
    """
    Обновляет товар по его ID, если он принадлежит текущему пользователю (только для 'seller')
    """
    # Проверка существования товара
    product = (
        await db.scalars(select(ProductModel)
                         .where(ProductModel.id == product_id,
                                ProductModel.is_active.is_(True)))
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    # Проверка принадлежности товара к продавцу
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only update your own products")

    # Проверка существования категории
    category = (
        await db.scalars(select(CategoryModel)
                         .where(CategoryModel.id == product.category_id,
                                CategoryModel.is_active.is_(True)))
    ).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found or inactive")

    # Обновление товара
    await db.execute(
        update(ProductModel)
        .where(ProductModel.id == product_id)
        .values(**payload.model_dump())
    )
    await db.commit()
    await db.refresh(product)
    return product

@router.delete("/{product_id}", response_model=ProductSchema, status_code=status.HTTP_200_OK)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: UserModel = Depends(get_current_seller)
):
    """
    Выполняет мягкое удаление товара, если он принадлежит текущему продавцу (только для 'seller')
    """
    # Проверка существования товара
    product = (
        await db.scalars(select(ProductModel)
                         .where(ProductModel.id == product_id,
                                ProductModel.is_active.is_(True)))
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or inactive")

    # Проверка принадлежности товара к продавцу
    if product.seller_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own products")

    # Логическое удаление товара (устанавление is_active=False)
    await db.execute(
        update(ProductModel)
        .where(ProductModel.id == product_id)
        .values(is_active=False)
    )
    await db.commit()
    await db.refresh(product)
    return product