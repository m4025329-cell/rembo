# Dockerfile для BlackLotusVPN (бот + вебап в одном контейнере)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные пакеты (минимум для aiohttp/sqlalchemy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Сначала зависимости — чтобы кешировался слой
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код
COPY . .

# Каталог под БД
RUN mkdir -p /app/db && chmod -R 777 /app/db

EXPOSE 8080

CMD ["python", "run.py"]
