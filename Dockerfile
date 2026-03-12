FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy

WORKDIR /app

# Install deps first for layer caching, then swap to CPU-only PyTorch
# (CUDA variant pulls ~7GB of nvidia/triton libs we don't need)
COPY pyproject.toml uv.lock* ./
RUN (uv sync --frozen --no-install-project 2>/dev/null || uv sync --no-install-project) \
    && uv pip install --reinstall \
         --index-url "https://download.pytorch.org/whl/cpu" \
         torch \
    && uv pip uninstall nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 \
         nvidia-cuda-nvrtc-cu12 nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 \
         nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cusolver-cu12 \
         nvidia-cusparse-cu12 nvidia-nccl-cu12 nvidia-nvjitlink-cu12 \
         nvidia-nvtx-cu12 triton 2>/dev/null; \
    rm -rf /root/.cache/uv

# Copy source and install project (re-swap torch to CPU after sync)
COPY . .
RUN (uv sync --frozen 2>/dev/null || uv sync) \
    && uv pip install --reinstall \
         --index-url "https://download.pytorch.org/whl/cpu" \
         torch \
    && uv pip uninstall nvidia-cublas-cu12 nvidia-cuda-cupti-cu12 \
         nvidia-cuda-nvrtc-cu12 nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12 \
         nvidia-cufft-cu12 nvidia-curand-cu12 nvidia-cusolver-cu12 \
         nvidia-cusparse-cu12 nvidia-nccl-cu12 nvidia-nvjitlink-cu12 \
         nvidia-nvtx-cu12 triton 2>/dev/null; \
    rm -rf /root/.cache/uv

CMD ["uv", "run", "python", "-m", "llm_pipeline.cli", "chat"]
