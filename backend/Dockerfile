FROM python:3.11-slim

# Install system fonts so PIL can render bold text in captcha images
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY captcha_service.py .

# .env is expected to be mounted at runtime (see docker-compose.yml)
# Never bake real secrets into the image.

EXPOSE 8080

CMD ["uvicorn", "captcha_service:app", "--host", "0.0.0.0", "--port", "8080"]
