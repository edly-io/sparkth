# -------------------
# Stage 1: Build dependencies
# -------------------
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# -------------------
# Stage 2: Runtime image
# -------------------
FROM python:3.14-slim-bookworm

RUN useradd -r appuser

WORKDIR /app

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv

COPY --chown=appuser:appuser . .

ENV PATH="/app/.venv/bin:$PATH"

USER appuser

CMD ["fastapi", "run", "app/main.py"]
