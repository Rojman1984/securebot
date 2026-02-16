FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY gateway_service.py .
COPY orchestrator.py .

EXPOSE 8080

CMD ["python", "gateway_service.py"]
