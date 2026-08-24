# -------------------
# Stage 1: Build frontend
# -------------------
FROM oven/bun:1.4.0 AS frontend-builder

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
# Stage 3: Compile translation catalogs
# -------------------
# pybabel lives in the dev dependency group, which must stay out of the runtime
# image. Compile the committed .po catalogs in a throwaway copy of the builder
# (dev group installed, still lockfile-pinned); the runtime stage takes only
# sparkth/locale, now holding the compiled .mo files the app loads.
FROM builder AS catalog-builder

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
RUN uv run --frozen pybabel compile -d sparkth/locale

# -------------------
# Stage 4: Runtime image
# -------------------
FROM python:3.14-slim-trixie

RUN apt-get update && apt-get install -y --no-install-recommends libjemalloc2 \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 999 nonroot \
 && useradd --system --gid 999 --uid 999 --create-home nonroot

COPY --from=builder      --chown=nonroot:nonroot /app            /app
COPY --from=catalog-builder --chown=nonroot:nonroot /app/sparkth/locale /app/sparkth/locale
COPY --from=frontend-builder --chown=nonroot:nonroot /frontend/out /app/frontend/out

ENV PATH="/app/.venv/bin:$PATH"
ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
# The production image bundles the frontend export and serves it from the
# backend; real env vars win over the .env default, so this stays on in k8s.
ENV SERVE_FRONTEND="true"

USER nonroot

WORKDIR /app

CMD ["fastapi", "run", "sparkth/main.py"]
