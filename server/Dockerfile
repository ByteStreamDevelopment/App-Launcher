FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends tzdata && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 1000 --create-home store && mkdir /data && chown store /data
WORKDIR /app
COPY *.py ./
COPY web ./web

ENV DB_PATH=/data/store.db \
    DATA_DIR=/data/files \
    PORT=8080 \
    TZ=Europe/Berlin \
    PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8080
USER store

HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"
CMD ["python", "store_server.py"]
