FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy

WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project

# Copy source and install project
COPY . .
RUN uv sync --frozen 2>/dev/null || uv sync

CMD ["uv", "run", "python", "-m", "llm_pipeline.cli", "chat"]
