FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --frozen --no-dev
CMD ["uv", "run", "text-to-gds"]
