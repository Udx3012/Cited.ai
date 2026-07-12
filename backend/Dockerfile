FROM python:3.11-slim

WORKDIR /app

# Install compilation dependencies and system binary tools (Tesseract, Poppler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Set environment defaults
ENV PORT=8000
ENV HOST=0.0.0.0

CMD ["sh", "-c", "uvicorn app.main:app --host $HOST --port $PORT"]
