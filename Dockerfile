FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATABASE_PATH=/app/runtime/clinic.db
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app/ backend/app/
COPY mock-data/ mock-data/
COPY --from=frontend /build/dist frontend/dist
RUN groupadd --gid 10001 clinic && useradd --uid 10001 --gid 10001 --create-home clinic && mkdir runtime && chown clinic:clinic runtime
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready',timeout=3).read()"]
CMD ["python","-m","uvicorn","app.main:create_app","--factory","--app-dir","backend","--host","0.0.0.0","--port","8000","--workers","1"]
