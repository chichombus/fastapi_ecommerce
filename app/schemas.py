from pydantic import BaseModel, Field, ConfigDict, EmailStr
from decimal import Decimal
from datetime import datetime

from app.enums import ProductSortField

class CategoryCreate(BaseModel):
    """
    Модель для создания и обновления категории.
    Используется в POST и PUT запросах.
    """
    name: str = Field(..., min_length=3, max_length=50,
                      description="Название категории (3-50 символов)")
    parent_id: int | None = Field(None, description="ID родительской категории, если есть")

class Category(BaseModel):
    """
    Модель для ответа с данными категории.
    Использутеся в GET запросах.
    """
    id: int = Field(..., description="Уникальный идентификатор товара")
    name: str = Field(..., description="Название категории")
    parent_id: int | None = Field(None, description="ID родительской категории, если есть")
    is_active: bool = Field(..., description="Активность категории")

    model_config = ConfigDict(from_attributes=True)

class ProductCreate(BaseModel):
    """
    Модель для создания и обновления товара.
    Используется в POST и PUT запросах.
    """
    name: str = Field(..., min_length=3, max_length=100,
                      description="Название товара (3-100 символов)")
    description: str | None = Field(None, max_length=500,
                                    description="Описание товара (до 500 символов)")
    price: Decimal = Field(..., gt=0, description="Цена товара (больше 0)", decimal_places=2)
    image_url: str | None = Field(None, max_length=200, description="URL изображения товара")
    stock: int = Field(..., ge=0, description="Количество товара на складе (0 или больше)")
    category_id: int = Field(..., description="ID категории, к которой относится товар")

class Product(BaseModel):
    """
    Модель для ответа с данными товара.
    Используется в GET запросах.
    """
    id: int = Field(..., description="Уникальный идентификатор товара")
    name: str = Field(..., description="Название товара")
    description: str | None = Field(None, description="Описание товара")
    price: Decimal = Field(..., description="Цена товара в рублях", gt=0, decimal_places=2)
    image_url: str | None = Field(None, description="URL изображение товара")
    stock: int = Field(..., description="Количество товара на складе")
    category_id: int = Field(..., description="ID категории")
    rating: float = Field(..., description="Рейтинг товара")
    is_active: bool = Field(..., description="Активность товара")

    model_config = ConfigDict(from_attributes=True)

class ProductRequest(BaseModel):
    """
    Модель запроса для формирования пагинации, фильтрации и поиска товаров
    """
    page: int = Field(ge=1, default=1, description="Номер страницы")
    page_size: int = Field(ge=1, le=100, default=20, description="Количество товаров на одной странице")
    category_id: int | None = Field(None, description="ID категории для фильтрации")
    search: str | None = Field(None, min_length=1, description="Поиск до названию товара")
    min_price: float | None = Field(None, ge=0, description="Минимальная цена товара")
    max_price: float | None = Field(None, ge=0, description="Максимальная цена товара")
    in_stock: bool | None = Field(None, description="True — только товары в наличии, False — только без остатка")
    seller_id: int | None = Field(None, description="ID продавца для фильтрации")
    sort_by: ProductSortField = Field(default=ProductSortField.id, description="Сортировка по полю")
    sort_direction: bool = Field(default=True, description="True - сортировка по возрастанию, False - по убыванию")

class ProductList(BaseModel):
    """
    Список пагинации для товаров
    """
    items: list[Product] = Field(description="Товары для текущей страницы")
    total: int = Field(ge=0, description="Общее количество товаров")
    page: int = Field(ge=1, description="Номер текущей страницы")
    page_size: int = Field(ge=1, description="Количество элементов на странице")

class UserCreate(BaseModel):
    email: EmailStr = Field(description="Email пользователя")
    password: str = Field(min_length=8, description="Пароль (минимум 8 символов)")
    role: str = Field(default="buyer", pattern="^(buyer|seller)$", description="Роль: 'buyer' или 'seller'")

class User(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор пользователя")
    email: EmailStr = Field(..., description="Email пользователя")
    is_active: bool = Field(..., description="Активность пользователя")
    role: str = Field(..., description="Роль пользователя")

    model_config = ConfigDict(from_attributes=True)

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="Старый refresh-токен")

class ReviewCreate(BaseModel):
    product_id: int = Field(..., description="ID товара")
    comment: str | None = Field(None, description="Текстовое поле для отызыва")
    grade: int = Field(..., description="Оценка товара") # Диапазон проверяется в POST эндпоинте

class Review(BaseModel):
    id: int = Field(..., description="Уникальный идентификатор отзыва")
    user_id: int = Field(..., description="ID пользователя")
    product_id: int = Field(..., description="ID товара")
    comment: str | None = Field(None, description="Текстовое поле для отызыва")
    comment_date: datetime = Field(..., description="Дата и время отзыва")
    grade: int = Field(..., description="Оценка товара")
    is_active: bool = Field(..., description="Активность отзыва")

    model_config = ConfigDict(from_attributes=True)