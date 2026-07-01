# Скрипт создания дашборда в Grafana через PowerShell
$GRAFANA_URL = "http://localhost:3000"
$USERNAME = "admin"
$PASSWORD = "admin123"

# Кодируем логин и пароль для Basic Auth
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${USERNAME}:${PASSWORD}"))

# JSON для дашборда
$dashboardJson = @'
{
  "dashboard": {
    "id": null,
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
  "overwrite": true
}
'@

try {
    # Отправляем запрос на создание дашборда
    $response = Invoke-RestMethod -Uri "${GRAFANA_URL}/api/dashboards/db" `
        -Method Post `
        -Headers @{
            "Authorization" = "Basic $base64AuthInfo"
            "Content-Type" = "application/json"
        } `
        -Body $dashboardJson `
        -UseBasicParsing
    
    Write-Host "✓ Dashboard created successfully!" -ForegroundColor Green
    Write-Host "URL: ${GRAFANA_URL}$($response.url)" -ForegroundColor Cyan
    
} catch {
    Write-Host "✗ Failed to create dashboard:" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    
    # Попробуем альтернативный метод
    try {
        Write-Host "Trying alternative method..." -ForegroundColor Yellow
        
        # Сначала проверим, доступен ли Prometheus из Grafana
        $testResult = Invoke-RestMethod -Uri "${GRAFANA_URL}/api/datasources" `
            -Method Get `
            -Headers @{
                "Authorization" = "Basic $base64AuthInfo"
            } `
            -UseBasicParsing
        
        Write-Host "✓ Grafana API accessible. Data sources:" -ForegroundColor Green
        $testResult | Format-Table -Property id, name, type, url
        
    } catch {
        Write-Host "✗ Cannot connect to Grafana API" -ForegroundColor Red
    }
}