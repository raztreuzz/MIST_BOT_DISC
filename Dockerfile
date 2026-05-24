FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Voice playback depends on ffmpeg.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

COPY pyproject.toml /app/
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main

COPY app /app/app

CMD ["python", "-m", "app.bot"]