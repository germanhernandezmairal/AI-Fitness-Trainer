FROM python:3.11-slim

WORKDIR /srv

# uv is how this project manages Python dependencies locally (see pyproject.toml/uv.lock) —
# installing it here keeps the container's dependency resolution identical to local dev instead
# of introducing a second, divergent pip-based install path.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN mkdir -p /srv/var/videos

EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
