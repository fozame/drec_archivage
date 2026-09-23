FROM python:3.11-slim

# libGL et libglib sont necessaires pour opencv-python-headless / rapidocr
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Volumes de donnees (montes par docker-compose)
RUN mkdir -p /data/uploads_temp /data/factures

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
