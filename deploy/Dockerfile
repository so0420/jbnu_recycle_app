# 1) 프론트 빌드
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 2) 백엔드 실행
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY data/ /app/data/
COPY --from=web /web/dist /app/frontend/dist
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.import_data --data /app/data && exec uvicorn main:app --host 127.0.0.1 --port 11010 --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-server-header"]
