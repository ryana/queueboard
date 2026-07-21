FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG BUILD_REVISION=dev

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    BUILD_REVISION=${BUILD_REVISION}

WORKDIR /app

COPY src ./src
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
RUN uv sync --frozen --no-dev

RUN groupadd --gid 10001 queueboard \
    && useradd --uid 10001 --gid queueboard --create-home queueboard \
    && chown -R queueboard:queueboard /app

USER queueboard

EXPOSE 8000
CMD ["uv", "run", "--no-sync", "uvicorn", "queueboard.main:app", "--host", "0.0.0.0", "--port", "8000"]
