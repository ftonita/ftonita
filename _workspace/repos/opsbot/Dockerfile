FROM python:3.12-slim
RUN useradd --create-home --uid 10001 opsbot
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
USER opsbot
# TELEGRAM_BOT_TOKEN is injected at runtime (secret / env), never baked into the image.
ENTRYPOINT ["opsbot"]
CMD ["run", "/config/opsbot.yml", "--audit-file", "/data/audit.jsonl"]
