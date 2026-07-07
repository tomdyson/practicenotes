FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY . .
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Build CSS and collect static assets at image build time. The secret key is
# a build-time placeholder only; the real one comes from the environment.
RUN DJANGO_DEBUG=false SECRET_KEY=build-placeholder ALLOWED_HOSTS=build \
    python manage.py tailwind build && \
    DJANGO_DEBUG=false SECRET_KEY=build-placeholder ALLOWED_HOSTS=build \
    python manage.py collectstatic --noinput

RUN chmod +x scripts/start.sh

EXPOSE 8000

CMD ["./scripts/start.sh"]
