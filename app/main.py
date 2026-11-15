from fastapi import FastAPI

from app.routers.categories import router as categories_router
from app.routers.products import router as products_router
from app.routers.users import router as users_router

# Создаем приложение FastAPI
app = FastAPI(
    title="FastAPI Интернет-магазин",
    version="0.1.0"
)

# Подключаем маршруты категорий
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(users_router)

# Корневой эндпоинт для проверки
@app.get("/")
async def root():
    """
    Корневой маршрут, подтверждающий, что API работает
    """
    return {"message": "Добро пожаловать в API Интернет-магазина"}