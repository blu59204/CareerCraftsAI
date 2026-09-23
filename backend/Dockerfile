FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt constraints.txt ./

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
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
# browser-use and python-jobspy conflict on markdownify version.
# Install browser-use with --no-deps, then install its deps minus markdownify,
# so python-jobspy's markdownify version wins (both work fine with 0.13.x).
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-deps browser-use==0.12.9 && \
    pip install --no-cache-dir -r requirements.txt -c constraints.txt && \
    playwright install chromium

COPY app/ ./app/
COPY memory/ ./memory/
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
