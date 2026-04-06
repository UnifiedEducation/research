# Stage 1: Build Next.js static frontend
FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Production build uses empty BACKEND_URL (same origin)
ENV NEXT_PUBLIC_BACKEND_URL=""
RUN npm run build

# Stage 2: Python backend + static frontend
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn[standard] msal requests python-dotenv pydantic

COPY backend/main.py .
COPY --from=frontend-build /frontend/out /app/static

ENV STATIC_DIR=/app/static
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
