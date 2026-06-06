FROM python:3.11-slim

WORKDIR /app

# Chromium runtime dependencies (replaces --with-deps which fails on Debian trixie)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    # Chromium shared libs
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_SYSTEM_PYTHON=1 \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml .
RUN uv sync --no-dev

# Install only the Chromium browser binary (system deps handled above)
RUN .venv/bin/playwright install chromium

COPY . .

# Artifact directories
RUN mkdir -p /app/artifacts/screenshots /app/artifacts/html_snapshots

CMD ["/app/.venv/bin/python", "-m", "app.main"]
