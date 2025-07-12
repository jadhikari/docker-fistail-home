# Fishtail Home - Hostel Management System

A professional Django-based hostel management system for managing student accommodations in Japan.

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### Development Setup
```bash
# Clone the repository
git clone <repository-url>
cd docker-fistail-home

# Create environment file (if not exists)
cp .env.dev.example .env.dev  # or create manually

# Edit environment variables
nano .env.dev

# Start development environment
make dev
```

### Production Setup
```bash
# Create environment file (if not exists)
cp .env.prod.example .env.prod  # or create manually

# Edit production environment variables
nano .env.prod

# Start production environment
make prod

# Run migrations
make migrate
```

## 📁 Project Structure

```
docker-fistail-home/
├── backend/                 # Django application
│   ├── accounts/           # User management
│   ├── customer/           # Customer/tenant management
│   ├── finance/            # Financial management
│   ├── hostel/             # Hostel management
│   ├── MIGRATION_RULES.md               # Simple migration rules
│   └── Dockerfile          # Multi-stage Docker build
├── nginx/                  # Nginx configuration
├── config/                 # Database configuration
├── docker-compose.dev.yml  # Development environment
├── docker-compose.prod.yml # Production environment
├── Makefile               # Management commands
└── README.md              # This file
```

## 🛠️ Available Commands

### Development
```bash
make dev              # Start development environment
make dev-detach       # Start development in background
make dev-logs         # Show development logs
make down-dev         # Stop development environment
```

### Production
```bash
make prod             # Start production environment
make prod-logs        # Show production logs
make down-prod        # Stop production environment
make restart          # Restart all services
```

### Database Management
```bash
make migrate          # Run migrations
make makemigrations   # Create new migrations
make backup           # Create database backup
make restore          # Restore from backup

# Migration Commands (SIMPLE)
make migration-status     # Check migration status
make migration-fake       # Fake migrations (when tables exist but migrations missing)
make migration-fake-initial # Fake initial migrations
```

### Maintenance
```bash
make clean            # Clean all Docker resources
make health           # Check service health
make monitor          # Monitor resource usage
```

### SSL Management
```bash
make ssl-setup        # Setup SSL certificates
make ssl-renew        # Renew SSL certificates
```

## 🔧 Configuration

### Environment Setup

The project uses separate environment files for development and production:

- **`.env.dev`**: Development environment variables
- **`.env.prod`**: Production environment variables

#### Manual Setup
```bash
# Create environment files manually
nano .env.dev    # For development
nano .env.prod   # For production
```

**Note**: The `.env.dev` and `.env.prod` files are already configured in the docker-compose files and are git-ignored for security.

Key configuration sections:
- **Django Settings**: Secret key, debug mode, allowed hosts
- **Database**: PostgreSQL (fishtaildb, user: fishtail)
- **Email**: SMTP configuration (companyfishtail@gmail.com)
- **SSL**: Certbot and domain settings (production)
- **Security**: CSRF, session, and security headers (production)

### Docker Configuration

The project uses multi-stage Docker builds for optimal security and performance:

- **Development**: Includes development tools and hot-reload
- **Production**: Minimal runtime with security hardening

### Nginx Configuration

Professional Nginx setup with:
- SSL/TLS optimization
- Security headers
- Rate limiting
- Gzip compression
- Static file caching
- Health checks

## 🔒 Security Features

- **Non-root containers**: All services run as non-root users
- **Security headers**: Comprehensive security headers in Nginx
- **Rate limiting**: API and login rate limiting
- **SSL/TLS**: Modern SSL configuration with HSTS
- **File upload validation**: Secure file upload handling
- **Environment isolation**: Separate dev/prod configurations

## 🚨 Security Alert - IMPORTANT

**CRITICAL**: If you received a GitGuardian alert about exposed credentials:

1. **Immediate Action Required**:
   ```bash
   # Create environment file with secure credentials
   cp .env.dev.example .env.dev
   nano .env.dev  # Edit with your secure password
   ```

2. **Set Environment Variables**:
   ```bash
   export POSTGRES_PASSWORD="your_secure_password_here"
   ```

3. **Update Docker Compose**:
   The docker-compose files now use environment variables instead of hardcoded passwords.

4. **Rotate Credentials**:
   - Change the database password
   - Update any other exposed credentials
   - Consider the credentials compromised

5. **Prevention**:
   - Never commit `.env` files to git
   - Use environment variables for all secrets
   - Regularly audit your codebase for hardcoded credentials

## 🛡️ Migration Rules

**SIMPLE RULE: Never delete migration files in production OR development**

This prevents the migration conflicts you've been experiencing.

### Quick Commands
```bash
# Check migration status
make migration-status

# Fix "relation already exists" error
make migration-fake-initial

# Fix missing migrations
make migration-fake
```

### Documentation
- **Simple Rules**: `backend/MIGRATION_RULES.md`

**That's it! Keep it simple.**

## 📊 Monitoring & Health Checks

All services include health checks:
- **Backend**: Django deployment check
- **Database**: PostgreSQL connection check
- **Redis**: Redis ping check
- **Nginx**: HTTP health endpoint

## 🚀 Deployment

### Development
```bash
make dev
# Access at http://localhost:8000
```

### Production
```bash
# 1. Configure environment (if not already done)
nano .env.prod

# 2. Start services
make prod

# 3. Run migrations
make migrate

# 4. Setup SSL (first time)
make ssl-setup

# 5. Create superuser
make createsuperuser
```

## 🔄 CI/CD Integration

The Docker setup is designed for easy CI/CD integration:

```yaml
# Example GitHub Actions workflow
- name: Build and deploy
  run: |
    make build-prod
    make prod
    make migrate
```

## 📝 Logging

Structured logging with log rotation:
- **Application logs**: `/app/logs/`
- **Nginx logs**: `/var/log/nginx/`
- **Docker logs**: JSON format with rotation

## 🔧 Troubleshooting

### Common Issues

1. **Port conflicts**: Check if ports 8000, 5432, 6379 are available
2. **Permission issues**: Ensure proper file permissions
3. **Database connection**: Verify PostgreSQL is running
4. **SSL issues**: Check certificate paths and permissions

### Debug Commands

```bash
make health           # Check service status
make logs-backend     # View backend logs
make logs-nginx       # View nginx logs
make shell            # Open Django shell
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `make test`
5. Submit a pull request

## 📄 License

This project is proprietary software for Fishtail Home management.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the troubleshooting section

---

**Fishtail Home Management System** - Professional hostel management for Japan

# docker-fistail-home

# Development environment variables env.dev
DJANGO_SECRET_KEY=django-insecure-dev-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1 0.0.0.0


# Production Environment Variables env.prod

DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SECRET_KEY=your_super_secret_production_key
DATABASE_URL=postgres://username:password@db:5432/yourdbname



#to run the projet 
dev
 docker-compose -f docker-compose.dev.yml up --build   
prod
 docker-compose -f docker-compose.prod.yml up --build   



 ### 3. Running in Development Mode

To start the project in development mode:

```sh
docker-compose -f docker-compose.dev.yml up --build
```

This will start the following services:

- **PostgreSQL**
- **Django Backend**
- **Nginx** (if included in the development setup)

### 4. Running in Production Mode

To deploy the project in production:

```sh
docker-compose -f docker-compose.prod.yml up --build -d
```

### 5. Accessing the Application

- **Django Backend API**: http://localhost:8000
- **Nginx Server**: http://localhost (if configured)

### 6. Managing the Database

To access the PostgreSQL database:

```sh
docker exec -it <postgres_container_id> psql -U postgres -d postgres
```

### 7. Running Migrations

Inside the backend container, run:

```sh
docker exec -it <backend_container_id> python manage.py migrate
```

### 8. Creating a Superuser

To create a Django superuser:

```sh
docker exec -it <backend_container_id> python manage.py createsuperuser
```

### 9. Stopping the Services

To stop the running containers:

```sh
docker-compose -f docker-compose.prod.yml down
```
### 10. Reset all 
1. **Stop and Remove All Containers**
Stop and remove all running containers to ensure no dependencies are active.
    ```sh
    docker stop $(docker ps -aq)
    ```
    ```sh
    docker rm $(docker ps -aq)
    ```
2. **Remove All Images**
Delete all Docker images.
    ```sh
    docker rmi $(docker images -q) -f
    ```
3. **Remove All Volumes**
Remove all Docker volumes.
    ```sh
    docker volume rm $(docker volume ls -q)
    ```
4. **Optional: Prune Everything (if you want a clean slate)**
To remove all unused containers, networks, images, and volumes, you can run the prune command:
    ```sh
    docker system prune -a --volumes -f
    ```

## Data Migration Process

To migrate data from one database to another (e.g., SQLite to MySQL), follow these steps:

### 1. Dump the Data
```sh
python manage.py dumpdata > datadump.json
```

### 2. Configure MySQL in `settings.py`
Modify your `settings.py` file to connect to your MySQL database. Ensure your MySQL server is running and has the correct permissions.

### 3. Apply Migrations
```sh
python manage.py migrate --run-syncdb
```

### 4. Remove ContentType Data
Run the following commands in the Django shell to exclude `ContentType` data:
```sh
python manage.py shell
```
Then, execute:
```python
from django.contrib.contenttypes.models import ContentType
ContentType.objects.all().delete()
quit()
```

### 5. Load the Dumped Data
```sh
python manage.py loaddata datadump.json
```
### Migrate from SQL Dump File
If you have an SQL dump file, you can restore it as follows:
```sh
docker exec -i <mysql_container_id> mysql -u <db_user> -p<db_password> <db_name> < dumpfile.sql
```
Ensure the database is created before running the import command.


# **PostgreSQL Database Reset and Import in Docker**

This guide provides step-by-step instructions on how to remove all data from a PostgreSQL database running in Docker and then import an SQL file into it.

---

## **1. Ensure Docker and PostgreSQL are Running**
Check if the PostgreSQL container is running:

```sh
docker ps
```

---

## **2. Terminate Active Connections**
Forcefully terminate all active connections to the database:

```sh
docker exec -it postgres-db-dev psql -U database_user -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='database_name';"
```

---

## **3. Drop and Recreate the Database**
Drop and recreate the database:

```sh
docker exec -it postgres-db-dev psql -U database_user -d postgres -c "DROP DATABASE database_name;"
docker exec -it postgres-db-dev psql -U database_user -d postgres -c "CREATE DATABASE database_name;"
```

---

## **4. Copy the SQL File into the Container**
Run this command on your host machine (not inside the container):

```sh
docker cp ~/pg/docker_base_solar_project/db_backup_20250217.sql postgres-db-dev:/tmp/backup.sql
```

---

## **5. Import the SQL File into PostgreSQL**
Enter the PostgreSQL container:

```sh
docker exec -it postgres-db-dev bash
```

Run the following command to import the SQL file:

```sh
psql -U database_user -d database_name -f /tmp/backup.sql
```

---

## **6. Verify the Import**
Check if the data has been imported successfully:

```sh
psql -U database_user -d database_name -c "SELECT * FROM your_table LIMIT 10;"
```

_(Replace `your_table` with an actual table name.)_

---

## **7. Exit the PostgreSQL Container**
After the process is complete, type:

```sh
exit
```

---

## **Conclusion**
Now your PostgreSQL database is successfully reset and restored! 🚀  
If you encounter any issues, double-check the container status and logs using:

```sh
docker logs postgres-db-dev
```

---



# Development environment variables
DJANGO_SECRET_KEY=django-insecure-dev-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1 0.0.0.0


🧪 How to Run It
Step-by-step when starting from scratch or updating:

# Start DB only first
docker-compose -f docker-compose.prod.yml up -d postgres

# Run migrations manually
docker-compose -f docker-compose.prod.yml run --rm migrate

# Start backend and nginx
docker-compose -f docker-compose.prod.yml up -d backend nginx
To re-run migrations:

docker-compose -f docker-compose.prod.yml run --rm migrate


Here's the deployment guide in **Markdown** format that you can add to your `README.md` or a separate `DEPLOYMENT.md`:

---

````markdown
# 🚀 Docker Deployment Guide

This guide explains the recommended steps for pulling the latest code, applying Django migrations, and restarting services when deploying updates to production.

---

## 📁 Prerequisites

- Docker and Docker Compose are installed
- You are inside the project directory on the production server

---

## 🔁 Step 1: Pull Latest Code

```bash
cd ~/your-project-directory
git pull origin main
````

---

## 🛠️ Step 2: Rebuild Docker Images (if needed)

If you've made changes to:

* `Dockerfile`
* `requirements.txt`
* `models.py`
* Django migrations

Then rebuild:

```bash
docker-compose -f docker-compose.prod.yml build
```

---

## ⚙️ Step 3: Apply Migrations

Use the `migrate` service defined in `docker-compose.prod.yml`:

```bash
docker-compose -f docker-compose.prod.yml run --rm migrate
```
```bash
docker-compose -f docker-compose.prod.yml run migrate
```

---

## 🔁 Step 4: Restart Backend (and Nginx if needed)

```bash
docker-compose -f docker-compose.prod.yml restart backend
```

If you've updated static files or Nginx config:

```bash
docker-compose -f docker-compose.prod.yml restart nginx
```

---
