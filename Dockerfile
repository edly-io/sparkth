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
# Stage 0: Build the bundled PXC activity's WASM sandbox
# -------------------
# componentize-js compiles the sample activity's sandbox to WebAssembly. The binary is a build
# product and is never committed (D2), so the image builds it rather than copying it in.
FROM node:22-trixie-slim AS pxc-activity-builder

RUN apt-get update && apt-get install -y --no-install-recommends make \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY package.json package-lock.json ./
RUN npm ci

COPY sparkth/plugins/pxc/activity/ ./sparkth/plugins/pxc/activity/
RUN make -C sparkth/plugins/pxc/activity build

# -------------------
# Stage 2: Build Python dependencies
# -------------------
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# uv clones the git-pinned pxc-lib during `uv sync`, and this image ships no git.
RUN apt-get update && apt-get install -y --no-install-recommends git \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*

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
# image. Compile the committed .po catalogs (core and per-plugin) in a throwaway
# copy of the builder (dev group installed, still lockfile-pinned); the runtime
# stage re-takes sparkth/, now holding the compiled .mo files the app loads.
FROM builder AS catalog-builder

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
RUN for dir in sparkth/locale sparkth/plugins/*/locale; do \
      uv run --frozen pybabel compile -d "$dir" || exit 1; \
    done

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
COPY --from=catalog-builder --chown=nonroot:nonroot /app/sparkth /app/sparkth
COPY --from=frontend-builder --chown=nonroot:nonroot /frontend/out /app/frontend/out
COPY --from=pxc-activity-builder --chown=nonroot:nonroot \
     /build/sparkth/plugins/pxc/activity/sandbox.wasm \
     /app/sparkth/plugins/pxc/activity/sandbox.wasm

ENV PATH="/app/.venv/bin:$PATH"
ENV LD_PRELOAD="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
# The production image bundles the frontend export and serves it from the
# backend; real env vars win over the .env default, so this stays on in k8s.
ENV SERVE_FRONTEND="true"

USER nonroot

WORKDIR /app

CMD ["fastapi", "run", "sparkth/main.py"]
