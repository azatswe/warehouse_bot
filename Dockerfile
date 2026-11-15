FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 bot \
    && useradd --system --uid 10001 --gid bot --home-dir /app bot \
    && install -d --owner=bot --group=bot /data

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY --chown=10001:10001 *.py ./
COPY --chown=10001:10001 handlers ./handlers

USER 10001:10001
CMD ["python", "main.py"]
