FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies for WeasyPrint and fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpango-1.0-0 \
    libharfbuzz0b \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project configuration
COPY pyproject.toml .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy application code and resources
COPY marketentry/ marketentry/
COPY templates/ templates/
COPY fixtures/ fixtures/

# Create output directories
RUN mkdir -p out fixtures/raw

EXPOSE 8000

CMD ["sh", "-c", "uvicorn marketentry.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
