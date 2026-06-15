# BeliefOS production image
# Multi-stage: build wheels in a builder image, copy into a slim runtime.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System dependencies for psycopg/bcrypt builds.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY beliefos ./beliefos

RUN pip wheel --wheel-dir=/wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BELIEFOS_ENV=production \
    BELIEFOS_HOST=0.0.0.0 \
    BELIEFOS_PORT=8000

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash beliefos

COPY --from=builder /wheels /wheels
COPY pyproject.toml README.md ./
COPY beliefos ./beliefos
COPY examples ./examples

RUN pip install --no-index --find-links=/wheels beliefos \
    && rm -rf /wheels

# Drop privileges.
USER beliefos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["uvicorn", "beliefos.api.app:create_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
