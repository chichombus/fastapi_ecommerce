from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, update, func, desc
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.products import Product as ProductModel
from app.models.categories import Category as CategoryModel
from app.models.users import User as UserModel
from app.models.reviews import Review as ReviewModel
from app.auth import get_current_seller
from app.schemas import ProductCreate, Product as ProductSchema, ProductList, ProductRequest, Review as ReviewSchema
from app.db_depends import get_db, get_async_db
from app.enums import ProductSortField

# Создаем маршрутизаторв для товаров
router = APIRouter(
    prefix="/products",
    tags=["products"]
)


@router.get("/", response_model=ProductList)
async def get_all_products(
    request: ProductRequest = Query(),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Возвращает список всех активных товаров с поддержкой фильтров и поиска
    """
    # Поддержка логики min_price <= max_price
    if request.min_price is not None and request.max_price is not None and request.min_price > request.max_price:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="min_price cannot be greater than max_price"
        )

    # Формируем список фильтров
    filters = [ProductModel.is_active == True]

    if request.category_id is not None:
        filters.append(ProductModel.category_id == request.category_id)
    if request.min_price is not None:
        filters.append(ProductModel.price >= request.min_price)
    if request.max_price is not None:
        filters.append(ProductModel.price <= request.max_price)
    if request.in_stock is not None:
        filters.append(ProductModel.stock > 0 if request.in_stock else ProductModel.stock == 0)
    if request.seller_id is not None:
        filters.append(ProductModel.seller_id == request.seller_id)

    rank_col = None
    if request.search:
        search_value = request.search.strip()
        if search_value:
            ts_query = func.websearch_to_tsquery('english', search_value)
            filters.append(ProductModel.tsv.op('@@')(ts_query))
            rank_col = func.ts_rank_cd(ProductModel.tsv, ts_query).label("rank")

    # Подсчет общего количества с учетом фильтров
    total_stmt = select(func.count()).select_from(ProductModel).where(*filters)
    total = await db.scalar(total_stmt) or 0

    # Формирование запроса сортировки
    sort_data = {
        ProductSortField.id: ProductModel.id,
        ProductSortField.created_at: ProductModel.created_at
    }

    order_by = sort_data[request.sort_by]
    if not request.sort_direction:
        order_by = order_by.desc()

    # Основной запрос (если есть поиск - добавим ранг в выборку и сортировку)
    if rank_col is not None:
        products_stmt = (
            select(ProductModel)
            .where(*filters)
            .order_by(desc(rank_col), order_by)
            .offset((request.page - 1) * request.page_size)
            .limit(request.page_size)
        )
        result = await db.execute(products_stmt)
        rows = result.all()
        items = [row[0] for row in rows]    # сами объекты
        # при желании можно вернуть ранг в ответе
        # ranks = [row.rank for row in rows]
    else:
        products_stmt = (
            select(ProductModel)
            .where(*filters)
            .order_by(order_by)
            .offset((request.page - 1) * request.page_size)
            .limit(request.page_size)
        )
        items = (await db.scalars(products_stmt)).all()


    return {
        "items": items,
        "total": total,
        "page": request.page,
        "page_size": request.page_size
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

@router.get("/reviews/{product_id}", response_model=list[ReviewSchema])
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
        .values(**payload.model_dump(), updated_at=func.now())
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