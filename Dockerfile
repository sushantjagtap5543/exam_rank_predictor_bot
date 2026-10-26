FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8080

WORKDIR /app

# Install system dependencies & Devanagari fonts for ReportLab PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-deva \
    fonts-indic \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose web ports for 24/7 cloud health checks (Render, Koyeb, Hugging Face Spaces)
EXPOSE 8080 7860 10000

# Run the Telegram bot daemon & health check web server 24/7
CMD ["python", "-m", "app.bot"]
