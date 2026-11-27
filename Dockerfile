# path: Dockerfile
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.12 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-install-project --no-dev
COPY app ./app
COPY web ./web
COPY docs/flows ./docs/flows
# Chạy bằng user không phải root; dùng thẳng virtualenv đã cài (uv chỉ dùng lúc build)
RUN useradd -r -u 1001 thienla && chown -R thienla /app
USER thienla
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
EXPOSE 4420
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4420"]
