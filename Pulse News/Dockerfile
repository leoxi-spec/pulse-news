FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PULSE_HOST=0.0.0.0 \
    PULSE_PORT=8787 \
    PULSE_DATA_DIR=/data

WORKDIR /app
COPY pulse ./pulse
COPY run.py ./
RUN mkdir -p /data && useradd -r -u 10001 pulse && chown -R pulse /data

USER pulse
VOLUME ["/data"]
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=4).status==200 else 1)"

CMD ["python3", "run.py"]
