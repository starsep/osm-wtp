FROM pypy:3.10-slim
WORKDIR /app
RUN apt-get update && \
    apt-get install --no-install-recommends -y git wget unzip &&\
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --no-dev

COPY . .
ENTRYPOINT ["/app/update-server.sh"]
