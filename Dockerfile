FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PULSE_HOST=0.0.0.0 \
    PULSE_DATA_DIR=/data

WORKDIR /app
COPY pulse ./pulse
COPY run.py ./
RUN mkdir -p /data && useradd -r -u 10001 pulse && chown -R pulse /data

USER pulse
VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python3 -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('PORT','8787')+'/api/health', timeout=4)"

CMD ["sh", "-c", "python3 run.py --host 0.0.0.0 --port ${PORT:-8787}"]
