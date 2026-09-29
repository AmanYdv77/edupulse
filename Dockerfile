# ==============================================================================
# Stage 1: Frontend Build Stage
# ==============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==============================================================================
# Stage 2: Python Runtime Stage
# ==============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PYTHONPATH=/app/backend:/app/backend/apps

# Install essential runtime tools (curl for healthchecks, libpq5 for PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN groupadd -r edupulse && useradd -r -g edupulse -d /home/edupulse -m edupulse

WORKDIR /app

# Install locked Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase, model artifacts, and frontend build assets
COPY backend/ ./backend/
COPY artifacts/ ./artifacts/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create staticfiles and artifact directories with correct non-root permissions
RUN mkdir -p /app/backend/staticfiles /app/artifacts/models \
    && chown -R edupulse:edupulse /app /home/edupulse

# Switch to unprivileged runtime user
USER edupulse

# Run collectstatic with dummy environment variables at build time
RUN DJANGO_ENV=prod \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    DJANGO_SECRET_KEY=build-time-dummy-secret-key-for-collectstatic-only-32chars \
    DJANGO_DEBUG=0 \
    DATABASE_URL=postgresql://dummy:dummy@localhost:5432/edupulse_dummy \
    MODEL_ARTIFACT_DIR=/app/artifacts/models \
    python backend/manage.py collectstatic --noinput

EXPOSE 8000

# Run migrations, register baseline model, and start Gunicorn dynamically binding to $PORT
CMD ["sh", "-c", "python backend/manage.py migrate --noinput && python backend/manage.py register_baseline_model && exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --threads 2 --access-logfile - --error-logfile -"]
