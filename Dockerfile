FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    UPDATE_INTERVAL_HOURS=6

WORKDIR /app

COPY requirements.txt .
# 当前无第三方依赖；有新增时取消注释下一行
# RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x /app/docker-entrypoint.sh \
    && mkdir -p /app/data /app/public/data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; p=os.environ.get('PORT','8080'); urllib.request.urlopen(f'http://127.0.0.1:{p}/api/health', timeout=3)"

ENTRYPOINT ["/app/docker-entrypoint.sh"]
