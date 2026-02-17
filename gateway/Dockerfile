FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common library
COPY common/ /app/common/

# Copy application files
COPY gateway/gateway_service.py .
COPY gateway/orchestrator.py .

EXPOSE 8080

CMD ["python", "gateway_service.py"]
