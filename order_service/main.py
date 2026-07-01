from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
import requests
from prometheus_client import Counter, Histogram, generate_latest, REGISTRY
from prometheus_client.exposition import CONTENT_TYPE_LATEST
import time
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus метрики
ORDER_REQUESTS = Counter('order_requests_total', 'Total order requests', ['method', 'endpoint'])
ORDER_REQUEST_DURATION = Histogram('order_request_duration_seconds', 'Order request duration')
ORDERS_CREATED = Counter('orders_created_total', 'Total orders created')
ORDER_VALUE = Histogram('order_value_rub', 'Order value distribution', buckets=[1000, 5000, 10000, 50000, 100000])

app = FastAPI(title="Order Service", version="1.0.0")

# Конфигурация
CATALOG_SERVICE_URL = "http://catalog_service:8001"

# Модели данных
class OrderItem(BaseModel):
    product_id: str
    quantity: int

class OrderCreate(BaseModel):
    customer_id: str
    items: List[OrderItem]
    shipping_address: str

class Order(BaseModel):
    id: str
    customer_id: str
    items: List[OrderItem]
    total_amount: float
    status: str  # "pending", "processing", "shipped", "delivered", "cancelled"
    created_at: datetime
    shipping_address: str

# In-memory хранилище
orders_db = []

@app.middleware("http")
async def monitor_requests(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    ORDER_REQUEST_DURATION.observe(duration)
    ORDER_REQUESTS.labels(method=request.method, endpoint=request.url.path).inc()
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
    # Проверяем доступность каталога
    try:
        catalog_response = requests.get(f"{CATALOG_SERVICE_URL}/health", timeout=2)
        catalog_status = catalog_response.json() if catalog_response.status_code == 200 else {"status": "unreachable"}
    except:
        catalog_status = {"status": "unreachable"}
    
    return {
        "status": "healthy",
        "service": "orders",
        "dependencies": {
            "catalog_service": catalog_status
        }
    }

@app.post("/orders", response_model=Order, status_code=201)
async def create_order(order_data: OrderCreate):
    start_time = time.time()
    
    # Проверяем наличие товаров и вычисляем стоимость
    total_amount = 0.0
    items_with_details = []
    
    for item in order_data.items:
        try:
            # Запрос к сервису каталога
            response = requests.get(
                f"{CATALOG_SERVICE_URL}/products/{item.product_id}/stock",
                timeout=5
            )
            
            if response.status_code == 200:
                stock_info = response.json()
                if stock_info['stock'] < item.quantity:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Недостаточно товара {item.product_id}. В наличии: {stock_info['stock']}"
                    )
                
                # Получаем информацию о товаре
                product_response = requests.get(
                    f"{CATALOG_SERVICE_URL}/products/{item.product_id}",
                    timeout=5
                )
                
                if product_response.status_code == 200:
                    product = product_response.json()
                    item_total = product['price'] * item.quantity
                    total_amount += item_total
                    items_with_details.append(item)
                else:
                    raise HTTPException(status_code=400, detail=f"Товар {item.product_id} не найден")
            else:
                raise HTTPException(status_code=400, detail=f"Товар {item.product_id} недоступен")
                
        except requests.RequestException as e:
            logger.error(f"Error contacting catalog service: {e}")
            raise HTTPException(status_code=503, detail="Catalog service unavailable")
    
    # Создаем заказ
    new_order = Order(
        id=str(uuid.uuid4()),
        customer_id=order_data.customer_id,
        items=items_with_details,
        total_amount=total_amount,
        status="pending",
        created_at=datetime.now(),
        shipping_address=order_data.shipping_address
    )
    
    orders_db.append(new_order)
    ORDERS_CREATED.inc()
    ORDER_VALUE.observe(total_amount)
    
    duration = time.time() - start_time
    logger.info(f"Order created: {new_order.id}, amount: {total_amount}, duration: {duration:.3f}s")
    
    return new_order

@app.get("/orders", response_model=List[Order])
async def get_orders(customer_id: Optional[str] = None, limit: int = 10):
    if customer_id:
        customer_orders = [o for o in orders_db if o.customer_id == customer_id]
        return customer_orders[:limit]
    return orders_db[:limit]

@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    for order in orders_db:
        if order.id == order_id:
            return order
    raise HTTPException(status_code=404, detail="Order not found")

@app.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    valid_statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]
    
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid statuses: {valid_statuses}")
    
    for order in orders_db:
        if order.id == order_id:
            order.status = status
            logger.info(f"Order {order_id} status updated to {status}")
            return {"message": "Status updated", "order_id": order_id, "status": status}
    
    raise HTTPException(status_code=404, detail="Order not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)