FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY mock-data/ mock-data/
COPY --from=frontend /build/dist frontend/dist
RUN useradd --create-home clinic && mkdir runtime && chown clinic:clinic runtime
USER clinic
EXPOSE 8000
CMD ["python","-m","uvicorn","app.main:create_app","--factory","--app-dir","backend","--host","0.0.0.0","--port","8000"]

