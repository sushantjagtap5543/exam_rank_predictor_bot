FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080 \
    APP_USER=appuser \
    APP_UID=10001

WORKDIR /app

# Install system dependencies & Devanagari fonts for ReportLab PDF generation + curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-deva \
    fonts-indic \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create secure non-root user
RUN groupadd --gid ${APP_UID} ${APP_USER} && \
    useradd --uid ${APP_UID} --gid ${APP_USER} --shell /bin/bash --create-home ${APP_USER}

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure appuser owns runtime directories
RUN chown -R ${APP_USER}:${APP_USER} /app

USER ${APP_USER}

# Expose web ports for 24/7 cloud health checks
EXPOSE 8080

# Health check to ensure service is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

CMD ["python", "-m", "app.bot"]
