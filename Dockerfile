FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080 \
    APP_USER=appuser \
    APP_UID=10001 \
    OPENCLAW_CONFIG_PATH=/home/appuser/.openclaw/openclaw.json

WORKDIR /app

# Install system dependencies, Devanagari fonts, GL/ONNX libraries & Node.js runtime for OpenClaw
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-deva \
    fonts-indic \
    ca-certificates \
    curl \
    gnupg \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g openclaw@latest --allow-scripts=openclaw \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# Create secure non-root user
RUN groupadd --gid ${APP_UID} ${APP_USER} && \
    useradd --uid ${APP_UID} --gid ${APP_USER} --shell /bin/bash --create-home ${APP_USER}

COPY requirements.txt .
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt

COPY . .

# Ensure appuser owns runtime directories, ~/.openclaw config and pre-create storage paths
RUN mkdir -p /app/admin_storage/products /app/data /app/products /home/${APP_USER}/.openclaw && \
    cp /app/openclaw.json /home/${APP_USER}/.openclaw/openclaw.json && \
    chown -R ${APP_USER}:${APP_USER} /app /home/${APP_USER}

USER ${APP_USER}

# Expose web ports for 24/7 cloud health checks and OpenClaw gateway
EXPOSE 8080 10000 18789

# Health check to ensure service is responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

CMD ["python", "-m", "app.bot"]
