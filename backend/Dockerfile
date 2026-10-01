FROM python:3.12-slim

WORKDIR /app
COPY requirements.lock provider-tools.txt ./

# Install system dependencies for Playwright
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    fonts-dejavu-core \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Exact versions from requirements.lock (compiled from requirements.txt +
# constraints.txt), then tools with obsolete upstream pins.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.lock && \
    pip install --no-cache-dir --no-deps -r provider-tools.txt && \
    playwright install chromium

COPY app/ ./app/
COPY memory/ ./memory/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
