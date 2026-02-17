FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY services/rag/requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY services/rag/rag_service.py .

# Expose port
EXPOSE 8400

# Run as non-root user (will be overridden by docker-compose user directive)
CMD ["python", "rag_service.py"]
