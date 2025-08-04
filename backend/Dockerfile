FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY ./backend /app

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# For dev: simple runserver
# For prod: use gunicorn
CMD ["/bin/sh", "-c", "if [ \"$DJANGO_DEBUG\" = \"True\" ]; then python manage.py runserver 0.0.0.0:8000; else gunicorn backend.wsgi:application --bind 0.0.0.0:8000; fi"]