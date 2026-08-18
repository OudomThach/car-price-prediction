# Car Price Prediction — containerized data pipeline
# Build:  docker build -t car-price-prediction .
# Run:    docker compose up (or docker run --rm -v ./data:/app/data car-price-prediction)

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install uv (fast, pinned for reproducibility)
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /usr/local/bin/

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application
COPY main.py ./
COPY car_price_prediction ./car_price_prediction

# Run as non-root
RUN useradd --create-home --uid 1000 scraper && mkdir -p /app/data /app/logs \
    && chown -R scraper:scraper /app
USER scraper

VOLUME ["/app/data", "/app/logs"]

CMD ["uv", "run", "python", "main.py"]
