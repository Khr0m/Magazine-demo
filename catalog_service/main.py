from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import List, Optional
import uuid
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
from prometheus_client.exposition import CONTENT_TYPE_LATEST
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus метрики
PRODUCT_REQUESTS = Counter('product_requests_total', 'Total product requests', ['method', 'endpoint'])
PRODUCT_REQUEST_DURATION = Histogram('product_request_duration_seconds', 'Product request duration')

app = FastAPI(title="Catalog Service", version="1.0.0")

# Модели данных
class Product(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    stock: int

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    category: str
    stock: int

# In-memory хранилище
products_db = [
    Product(id="1", name="Ноутбук Dell XPS", description="15.6 дюймов, 16 ГБ ОЗУ, 512 ГБ SSD", price=89999.99, category="Электроника", stock=10),
    Product(id="2", name="Смартфон iPhone 15", description="128 ГБ, черный", price=79999.99, category="Электроника", stock=25),
    Product(id="3", name="Наушники Sony WH-1000XM5", description="Беспроводные, шумоподавление", price=29999.99, category="Аудио", stock=15),
]

@app.middleware("http")
async def monitor_requests(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    PRODUCT_REQUEST_DURATION.observe(duration)
    PRODUCT_REQUESTS.labels(method=request.method, endpoint=request.url.path).inc()
    logger.info(f"{request.method} {request.url.path} - {duration:.3f}s")
    return response

@app.get("/metrics")
async def metrics():
    """Эндпоинт для метрик Prometheus"""
    # Генерируем метрики в текстовом формате
    metrics_data = generate_latest(REGISTRY)
    
    # Возвращаем как текст с правильным content-type
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "catalog"}

@app.get("/products", response_model=List[Product])
async def get_products(category: Optional[str] = None):
    if category:
        return [p for p in products_db if p.category == category]
    return products_db

@app.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    for product in products_db:
        if product.id == product_id:
            return product
    raise HTTPException(status_code=404, detail="Product not found")

@app.post("/products", response_model=Product, status_code=201)
async def create_product(product_data: ProductCreate):
    new_product = Product(
        id=str(uuid.uuid4()),
        **product_data.dict()
    )
    products_db.append(new_product)
    logger.info(f"Created product: {new_product.name}")
    return new_product

@app.get("/products/{product_id}/stock")
async def get_stock(product_id: str):
    for product in products_db:
        if product.id == product_id:
            return {"product_id": product_id, "stock": product.stock}
    raise HTTPException(status_code=404, detail="Product not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)