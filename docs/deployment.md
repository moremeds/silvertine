# Silvertine Deployment Guide

This guide covers deployment options and production setup for the Silvertine trading system.

## Deployment Overview

Silvertine supports multiple deployment configurations:
- **Local Development**: Single machine with local Redis
- **Docker Container**: Containerized deployment with external dependencies
- **Cloud VPS**: Virtual private server deployment
- **Kubernetes**: Scalable container orchestration

## Prerequisites

### System Requirements
- **CPU**: 2+ cores (4+ recommended for production)
- **RAM**: 4GB minimum (8GB+ recommended for production)
- **Storage**: 20GB+ SSD storage
- **Network**: Stable internet connection with low latency to exchanges

### Software Dependencies
- **Python**: 3.11 or higher
- **Redis**: 6.0 or higher
- **Docker**: 20.10+ (for containerized deployment)
- **Git**: For source code management

## Local Development Deployment

### 1. Environment Setup
```bash
# Clone repository
git clone <repository-url>
cd silvertine

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 2. Configuration
```bash
# Copy configuration templates
cp config/environments/development.yaml.example config/environments/development.yaml
cp config/exchanges/binance_testnet.yaml.example config/exchanges/binance_testnet.yaml
cp .env.example .env

# Edit configuration files with your settings
nano config/environments/development.yaml
nano .env
```

### 3. Start Services
```bash
# Start Redis server (separate terminal)
redis-server

# Start Silvertine
make run
```

## Docker Deployment

### 1. Dockerfile
Create a production Dockerfile:

```dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY config/ ./config/
COPY pyproject.toml .

# Create cache directory
RUN mkdir -p silver_cache/sqlite silver_cache/logs silver_cache/temp silver_cache/redis

# Create non-root user
RUN useradd -m -u 1000 silvertine && \
    chown -R silvertine:silvertine /app
USER silvertine

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Expose port
EXPOSE 8000

# Start application
CMD ["python", "-m", "src.main"]
```

### 2. Docker Compose
Create `docker-compose.yml` for full stack:

```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  silvertine:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./config:/app/config:ro
      - ./cache:/app/cache
      - ./.env:/app/.env:ro
    environment:
      - REDIS_URL=redis://redis:6379
      - ENVIRONMENT=production
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

volumes:
  redis_data:
  grafana_data:
```

### 3. Build and Deploy
```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f silvertine

# Stop services
docker-compose down
```

## Cloud VPS Deployment

### 1. Server Setup (Ubuntu 22.04)
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Install Redis
sudo apt install -y redis-server

# Install Docker (optional)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install nginx (for reverse proxy)
sudo apt install -y nginx
```

### 2. Application Deployment
```bash
# Create application user
sudo useradd -m -s /bin/bash silvertine
sudo su - silvertine

# Clone and setup application
git clone <repository-url>
cd silvertine
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup configuration
cp config/environments/production.yaml.example config/environments/production.yaml
# Edit configuration files...

# Setup systemd service
sudo nano /etc/systemd/system/silvertine.service
```

### 3. Systemd Service
Create `/etc/systemd/system/silvertine.service`:

```ini
[Unit]
Description=Silvertine Trading System
After=network.target redis.service
Requires=redis.service

[Service]
Type=simple
User=silvertine
Group=silvertine
WorkingDirectory=/home/silvertine/silvertine
Environment=PATH=/home/silvertine/silvertine/venv/bin
ExecStart=/home/silvertine/silvertine/venv/bin/python -m src.main
Restart=always
RestartSec=10

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/home/silvertine/silvertine/cache

[Install]
WantedBy=multi-user.target
```

### 4. Nginx Reverse Proxy
Create `/etc/nginx/sites-available/silvertine`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5. Enable and Start Services
```bash
# Enable and start services
sudo systemctl enable redis-server
sudo systemctl enable silvertine
sudo systemctl start silvertine

# Enable nginx
sudo ln -s /etc/nginx/sites-available/silvertine /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Check status
sudo systemctl status silvertine
```

## Kubernetes Deployment

### 1. Namespace and ConfigMap
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: silvertine

---
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: silvertine-config
  namespace: silvertine
data:
  development.yaml: |
    debug: false
    log_level: INFO
    environment: production
    # ... rest of configuration
```

### 2. Deployment
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: silvertine
  namespace: silvertine
spec:
  replicas: 2
  selector:
    matchLabels:
      app: silvertine
  template:
    metadata:
      labels:
        app: silvertine
    spec:
      containers:
      - name: silvertine
        image: silvertine:latest
        ports:
        - containerPort: 8000
        env:
        - name: REDIS_URL
          value: "redis://redis:6379"
        - name: ENVIRONMENT
          value: "production"
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: cache
          mountPath: /app/cache
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
      volumes:
      - name: config
        configMap:
          name: silvertine-config
      - name: cache
        emptyDir: {}
```

### 3. Service and Ingress
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: silvertine
  namespace: silvertine
spec:
  selector:
    app: silvertine
  ports:
  - port: 8000
    targetPort: 8000
  type: ClusterIP

---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: silvertine
  namespace: silvertine
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
spec:
  rules:
  - host: your-domain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: silvertine
            port:
              number: 8000
```

## Monitoring and Observability

### 1. Prometheus Configuration
Create `monitoring/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'silvertine'
    static_configs:
      - targets: ['silvertine:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

### 2. Grafana Dashboard
Import the provided Grafana dashboard for Silvertine metrics:
- System performance (CPU, memory, latency)
- Trading metrics (P&L, positions, orders)
- Risk metrics (drawdown, exposure, violations)

## Security Considerations

### 1. Network Security
- Use firewalls to restrict access to necessary ports only
- Enable fail2ban for SSH protection
- Use VPN for remote administration access

### 2. Application Security
- Store secrets in environment variables or secret management systems
- Enable TLS/SSL for all external communications
- Implement rate limiting and request validation
- Regular security updates and vulnerability scanning

### 3. Access Control
- Use strong authentication and authorization
- Implement role-based access control (RBAC)
- Regular audit of user access and permissions
- Enable audit logging for all administrative actions

## Backup and Disaster Recovery

### 1. Data Backup
```bash
# Database backup
sqlite3 silver_cache/sqlite/silvertine.db ".backup silver_cache/backups/silvertine_$(date +%Y%m%d_%H%M%S).db"

# Configuration backup
tar -czf config_backup_$(date +%Y%m%d_%H%M%S).tar.gz config/

# Redis backup
redis-cli --rdb silver_cache/backups/redis_$(date +%Y%m%d_%H%M%S).rdb
```

### 2. Disaster Recovery Plan
1. **Data Recovery**: Restore from latest backup
2. **Configuration Recovery**: Deploy from version control
3. **Service Recovery**: Restart services with health checks
4. **Validation**: Verify system functionality and data integrity

## Performance Tuning

### 1. System Optimization
- Tune kernel parameters for network performance
- Optimize Redis configuration for trading workload
- Configure appropriate ulimits for file descriptors
- Use SSD storage for database and cache

### 2. Application Optimization
- Monitor and tune asyncio event loop performance
- Optimize database queries and connection pooling
- Implement caching for frequently accessed data
- Profile and optimize hot code paths

## Troubleshooting

### Common Issues
1. **Connection Issues**: Check network connectivity and firewall rules
2. **Performance Issues**: Monitor system resources and optimize bottlenecks
3. **Data Issues**: Verify data integrity and backup/restore procedures
4. **Configuration Issues**: Validate configuration files and environment variables

### Log Locations
- **Application Logs**: `silver_cache/logs/`
- **System Logs**: `/var/log/syslog`
- **Nginx Logs**: `/var/log/nginx/`
- **Redis Logs**: `/var/log/redis/`

## See Also

- [Architecture Documentation](architecture.md) - System architecture overview
- [API Documentation](api.md) - REST API and WebSocket endpoints
- [Development Guide](development.md) - Development workflow and best practices