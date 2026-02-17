FROM python:3.11-slim

WORKDIR /app

# Copy requirements
COPY vault/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common library
COPY common/ /app/common/

# Copy application files
COPY vault/vault_service.py .

EXPOSE 8200

CMD ["python", "vault_service.py"]
