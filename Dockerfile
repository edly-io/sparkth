# Use Rust 1.88 slim image for building
FROM rust:1.88-slim-bookworm AS builder

# Set working directory
WORKDIR /usr/src/sparkth

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Define build profile (default: dist)
ARG PROFILE=dist

# Build and strip binary
RUN cargo build --profile ${PROFILE} --locked && \
    strip target/${PROFILE}/sparkth

# Use slim Debian image for runtime
FROM debian:bookworm-slim

# Reuse build profile argument
ARG PROFILE=dist

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy built binary from builder stage
COPY --from=builder /usr/src/sparkth/target/${PROFILE}/sparkth /usr/local/bin/sparkth

# Expose port 7727
EXPOSE 7727

# Set environment variables for host and port
ENV HOST=0.0.0.0
ENV PORT=7727

# Run the application
CMD ["sh", "-c", "sparkth --host $HOST --port $PORT"]
