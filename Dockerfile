# ---- 前端构建 ----
# 镜像内自带一份 dist：线上 Nginx 仍优先直发 /app/，这份是无害冗余，
# 同时也是前端的第二个回滚源（Nginx 目录被改坏时可从镜像取回）。
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 运行时 ----
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONFAULTHANDLER=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py ./server.py
COPY backend ./backend
COPY core ./core
COPY config ./config
COPY assets ./assets
COPY --from=web /web/dist ./web/dist

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=3).read()"

# --proxy-headers 让 uvicorn 采纳 X-Forwarded-For。容器只监听 127.0.0.1 映射、
# 外部流量必经 Nginx，所以 forwarded-allow-ips 用 * 可接受。
# 缺了它，登录限流会退化成全站共用一个桶，审计 IP 也全是网桥网关。
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
