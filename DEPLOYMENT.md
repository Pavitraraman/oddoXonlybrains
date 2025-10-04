# Deployment Guide - Expense Management System

This guide provides detailed instructions for deploying the Expense Management System in various environments.

## 🚀 Quick Deployment

### Prerequisites
- Docker and Docker Compose
- Git
- Basic knowledge of Linux/Unix commands

### One-Command Setup
```bash
# Clone the repository
git clone <https://github.com/Pavitraraman/oddoXonlybrains.gitl>
cd expense-management-system

# Run the setup script
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The system will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs

## 🔧 Environment Configuration

### Required Environment Variables

Create a `.env` file with the following variables:

```bash
# Email Configuration (REQUIRED for notifications)
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=noreply@yourcompany.com

# Security (CHANGE IN PRODUCTION!)
SECRET_KEY=your-super-secret-key-change-in-production

# Optional: Exchange Rate API
EXCHANGE_RATE_API_KEY=your-api-key
```

### Email Setup (Gmail)
1. Enable 2-factor authentication on your Gmail account
2. Generate an "App Password" for the application
3. Use the app password in `SMTP_PASSWORD`

### Exchange Rate API (Optional)
- Sign up at https://exchangerate-api.com/
- Get your free API key
- Add it to `EXCHANGE_RATE_API_KEY`

## 🐳 Docker Deployment

### Development Environment
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Environment
```bash
# Use production configuration
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Service Management
```bash
# Restart specific service
docker-compose restart backend

# Scale services
docker-compose up -d --scale celery_worker=3

# Update services
docker-compose pull
docker-compose up -d
```

## ☁️ Cloud Deployment

### AWS Deployment

#### Using AWS ECS with Fargate
1. **Create ECR repositories**:
```bash
aws ecr create-repository --repository-name expense-management-backend
aws ecr create-repository --repository-name expense-management-frontend
```

2. **Build and push images**:
```bash
# Build and tag images
docker build -t expense-management-backend ./backend
docker build -t expense-management-frontend ./frontend

# Tag for ECR
docker tag expense-management-backend:latest <account-id>.dkr.ecr.<region>.amazonaws.com/expense-management-backend:latest
docker tag expense-management-frontend:latest <account-id>.dkr.ecr.<region>.amazonaws.com/expense-management-frontend:latest

# Push to ECR
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/expense-management-backend:latest
docker push <account-id>.dkr.ecr.<region>.amazonaws.com/expense-management-frontend:latest
```

3. **Set up RDS PostgreSQL**:
   - Create RDS PostgreSQL instance
   - Configure security groups
   - Update connection string in environment variables

4. **Set up ElastiCache Redis**:
   - Create ElastiCache Redis cluster
   - Configure security groups
   - Update Redis URL in environment variables

#### Using AWS App Runner
1. Create `apprunner.yaml`:
```yaml
version: 1.0
runtime: python3
build:
  commands:
    build:
      - echo "Build started on `date`"
      - pip install -r requirements.txt
run:
  runtime-version: 3.11
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000
  network:
    port: 8000
    env: PORT
  env:
    - name: DATABASE_URL
      value: postgresql+asyncpg://user:password@rds-endpoint:5432/expense_management
```

### Google Cloud Platform

#### Using Cloud Run
```bash
# Build and deploy backend
gcloud builds submit --tag gcr.io/PROJECT-ID/expense-backend ./backend
gcloud run deploy expense-backend --image gcr.io/PROJECT-ID/expense-backend --platform managed --region us-central1 --allow-unauthenticated

# Build and deploy frontend
gcloud builds submit --tag gcr.io/PROJECT-ID/expense-frontend ./frontend
gcloud run deploy expense-frontend --image gcr.io/PROJECT-ID/expense-frontend --platform managed --region us-central1 --allow-unauthenticated
```

### DigitalOcean

#### Using App Platform
1. Connect your GitHub repository
2. Configure build settings:
   - **Backend**: Python buildpack, command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Frontend**: Node.js buildpack, command: `npm start`

3. Add environment variables in the App Platform dashboard
4. Set up managed PostgreSQL and Redis databases

## 🔒 Production Security

### SSL/TLS Configuration
```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;
    
    ssl_certificate /etc/ssl/certs/your-domain.crt;
    ssl_certificate_key /etc/ssl/private/your-domain.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    
    # Rest of your configuration...
}
```

### Environment Security
```bash
# Generate secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Use environment-specific configurations
export SECRET_KEY="your-secure-secret-key"
export DEBUG=False
export ALLOWED_HOSTS="your-domain.com,www.your-domain.com"
```

### Database Security
- Use strong passwords
- Enable SSL connections
- Restrict database access to application servers only
- Regular security updates
- Enable connection pooling

## 📊 Monitoring and Logging

### Application Monitoring
```bash
# View application logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Monitor resource usage
docker stats

# Check service health
curl http://localhost:8000/health
curl http://localhost:3000/health
```

### Database Monitoring
```sql
-- Check database connections
SELECT count(*) FROM pg_stat_activity;

-- Check database size
SELECT pg_size_pretty(pg_database_size('expense_management'));

-- Check slow queries
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;
```

### Log Aggregation
Consider using:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Fluentd** for log forwarding
- **Prometheus + Grafana** for metrics
- **Sentry** for error tracking

## 🔄 Backup and Recovery

### Database Backups
```bash
# Create backup
docker-compose exec postgres pg_dump -U expense_user expense_management > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
docker-compose exec -T postgres psql -U expense_user expense_management < backup.sql
```

### Automated Backups
```bash
# Add to crontab
0 2 * * * docker-compose exec postgres pg_dump -U expense_user expense_management > /backups/backup_$(date +\%Y\%m\%d_\%H\%M\%S).sql
```

### File Backups
```bash
# Backup uploads directory
tar -czf uploads_backup_$(date +%Y%m%d_%H%M%S).tar.gz backend/uploads/
```

## 🚀 Scaling

### Horizontal Scaling
```yaml
# docker-compose.yml
services:
  backend:
    deploy:
      replicas: 3
  
  celery_worker:
    deploy:
      replicas: 5
  
  frontend:
    deploy:
      replicas: 2
```

### Load Balancing
```nginx
upstream backend {
    server backend1:8000;
    server backend2:8000;
    server backend3:8000;
}

upstream frontend {
    server frontend1:3000;
    server frontend2:3000;
}
```

### Database Scaling
- Use read replicas for reporting queries
- Implement connection pooling (PgBouncer)
- Consider database sharding for large datasets

## 🔧 Maintenance

### Regular Tasks
1. **Weekly**:
   - Review system logs
   - Check disk space
   - Update dependencies

2. **Monthly**:
   - Database optimization
   - Security updates
   - Performance review

3. **Quarterly**:
   - Full system backup
   - Disaster recovery testing
   - Capacity planning

### Update Process
```bash
# Pull latest changes
git pull origin main

# Update images
docker-compose pull

# Rebuild if needed
docker-compose build

# Restart services
docker-compose up -d

# Run migrations
docker-compose exec backend alembic upgrade head
```

## 🆘 Troubleshooting

### Common Issues

#### Database Connection Issues
```bash
# Check database status
docker-compose exec postgres pg_isready -U expense_user

# Check connection logs
docker-compose logs postgres
```

#### Email Delivery Issues
```bash
# Test email configuration
docker-compose exec backend python -c "
from app.services.notification_service import notification_service
print('SMTP configuration test')
"
```

#### File Upload Issues
```bash
# Check upload directory permissions
ls -la backend/uploads/

# Fix permissions if needed
chmod 755 backend/uploads/
```

#### Performance Issues
```bash
# Check resource usage
docker stats

# Check database performance
docker-compose exec postgres psql -U expense_user -d expense_management -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
"
```

### Health Checks
```bash
# Backend health
curl -f http://localhost:8000/health

# Frontend health
curl -f http://localhost:3000/health

# Database health
docker-compose exec postgres pg_isready -U expense_user

# Redis health
docker-compose exec redis redis-cli ping
```

## 📞 Support

For deployment support:
1. Check the logs: `docker-compose logs -f`
2. Review this documentation
3. Check the main README.md
4. Create an issue in the repository

---

**Happy Deploying! 🚀**

