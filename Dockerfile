# =========================
# 1. Base Python Image
# =========================
FROM python:3.11-slim

# Avoid interactive prompts
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && apt-get clean

# =========================
# 2. Set Work Directory
# =========================
WORKDIR /app

# Copy requirement files
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy full project
COPY . /app/

# =========================
# 3. Django Environment
# =========================
ENV DJANGO_SETTINGS_MODULE=backend.settings

# Collect static files
RUN python manage.py collectstatic --noinput || true

# =========================
# 4. Expose Port
# =========================
EXPOSE 8000

# =========================
# 5. Prefect + Chroma
# Chroma will write to /chroma which will be backed by Render Disk
# =========================
ENV CHROMA_DISK_PATH=/chroma

# Create directory for chroma storage
RUN mkdir -p /chroma

# =========================
# 6. Start Command (Gunicorn + Prefect)
# =========================
CMD gunicorn backend.wsgi:application --bind 0.0.0.0:8000 --timeout 200
