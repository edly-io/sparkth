# -------------------
# Stage 1: Build frontend
# -------------------
FROM oven/bun:1 AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/bun.lock ./
# TODO we should install non-dev dependencies with `--production` but right now this is
# failing with missing typescript dependency.
RUN bun install --frozen-lockfile

COPY frontend/ ./
RUN bun run build

# -------------------
# Stage 2: Build Python dependencies
# -------------------
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY . /app

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# -------------------
# Stage 3: Runtime image
# -------------------
FROM python:3.14-slim-trixie

RUN apt-get update && apt-get install -y --no-install-recommends libjemalloc2 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

COPY --from=builder      --chown=nonroot:nonroot /app            /app
COPY --from=frontend-builder --chown=nonroot:nonroot /frontend/out /app/frontend/out

ENV PATH="/app/.venv/bin:$PATH"
ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"

USER nonroot

WORKDIR /app

CMD ["fastapi", "run", "app/main.py"]
