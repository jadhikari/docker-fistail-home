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
