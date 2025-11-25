FROM python:3.11-slim-bookworm

# 1. Cài đặt thư viện hệ thống (QUAN TRỌNG CHO WEASYPRINT & POSTGRES)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    python3-dev \
    # Thư viện cho WeasyPrint (PDF)
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Cài đặt thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy code
COPY . .

# 4. Tạo thư mục static và media
RUN mkdir -p /app/staticfiles /app/media

# 5. Thu thập file tĩnh
RUN python manage.py collectstatic --noinput

# 6. Lệnh khởi chạy (Tự động Migrate DB)
CMD sh -c "python manage.py migrate && gunicorn config.wsgi:application --bind 0.0.0.0:$PORT"