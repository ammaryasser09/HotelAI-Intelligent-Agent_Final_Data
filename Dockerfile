# The backend API as a container image. Built by docker-compose.yml (docker compose up -d --build).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Africa/Cairo

WORKDIR /srv

# dependencies first: this layer is reused as long as requirements-api.txt does not change
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# only what the API needs: its code and the photos it serves
COPY app/__init__.py app/__init__.py
COPY app/api app/api
COPY static static

# never run as root inside the container
RUN useradd --create-home hotel && mkdir -p logs && chown hotel logs
USER hotel

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# One process: the live chat remembers who is connected in memory (several processes would need Redis).
# --proxy-headers: behind Caddy (HTTPS), the API sees the guest's real address, for the rate limit and the logs.
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
