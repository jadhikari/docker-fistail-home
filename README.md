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