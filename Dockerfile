# 1) Frontend
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2) Producción: FastAPI sirve la API y el frontend compilado
FROM python:3.12-slim AS produccion
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ENTORNO=produccion \
    CARPETA_FRONTEND=/app/frontend/dist PADRON_CARPETA=/tmp/padron
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend /app/frontend/dist /app/frontend/dist
RUN useradd --uid 1001 --create-home app && mkdir -p /tmp/padron && chown app /tmp/padron
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
