import json
import requests
import time

# Конфигурация
GRAFANA_URL = "http://localhost:3000"
USERNAME = "admin"
PASSWORD = "admin123"

# Создаем сессию
session = requests.Session()
session.auth = (USERNAME, PASSWORD)

# Дашборд в формате JSON
dashboard_json = {
    "dashboard": {
        "id": None,
        "title": "Ecommerce Monitoring",
        "panels": [
            {
                "id": 1,
                "title": "Service Health",
                "type": "stat",
                "targets": [
                    {
                        "expr": "up{job=~\"catalog-service|order-service\"}",
                        "legendFormat": "{{job}}"
                    }
                ],
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0}
            },
            {
                "id": 2,
                "title": "HTTP Requests",
                "type": "graph",
                "targets": [
                    {
                        "expr": "rate(product_requests_total[5m])",
                        "legendFormat": "Catalog"
                    },
                    {
                        "expr": "rate(order_requests_total[5m])",
                        "legendFormat": "Orders"
                    }
                ],
                "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
            }
        ],
        "time": {"from": "now-1h", "to": "now"}
    },
    "folderId": 0,
    "overwrite": True
}

# Отправляем запрос на создание дашборда
try:
    response = session.post(
        f"{GRAFANA_URL}/api/dashboards/db",
        json=dashboard_json,
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code == 200:
        print("✓ Dashboard created successfully!")
        print(f"URL: {GRAFANA_URL}{response.json()['url']}")
    else:
        print(f"✗ Failed to create dashboard: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"✗ Error: {str(e)}")