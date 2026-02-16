FROM python:3.11-slim

WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY vault_service.py .

EXPOSE 8200

CMD ["python", "vault_service.py"]
