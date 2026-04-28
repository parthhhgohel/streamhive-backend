FROM python:3.11-slim

# Prevent .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements/ requirements/
RUN pip install --upgrade pip
RUN pip install -r requirements/development.txt

# Copy project
COPY . .

# Run collectstatic before default command
RUN python manage.py collectstatic --noinput --settings=backend.settings.production

# Expose port
EXPOSE 8000

# Default command (can override in compose)
# CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

CMD ["gunicorn", "backend.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]