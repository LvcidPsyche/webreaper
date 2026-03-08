# ===========================================================================
# WebReaper — Dockerfile
# ===========================================================================
# Build:  docker build -t webreaper .
# Run:    docker run -p 8000:8000 --env-file .env webreaper
# ===========================================================================

FROM python:3.11-slim AS base

# System deps for lxml, playwright, and whois
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt-dev \
    libffi-dev \
    whois \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------------------------
# Python dependencies (production only — no dev/test deps)
# ---------------------------------------------------------------------------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only — ~170MB)
RUN playwright install chromium --with-deps

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
COPY . .

# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------
ENV APP_ENV=production
ENV HOST=0.0.0.0
ENV PORT=8000

# Non-root user for security
RUN useradd -m -u 1000 webreaper && \
    mkdir -p /home/webreaper/.webreaper && \
    chown -R webreaper:webreaper /app /home/webreaper
USER webreaper

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run DB migrations then start server
CMD ["sh", "-c", "alembic upgrade head && python webreaper.py"]
