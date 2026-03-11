FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml .
RUN uv sync --no-dev --no-install-project

# Copy source
COPY src/ src/

# Install the project itself
RUN uv sync --no-dev

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "production_mcp.server"]
