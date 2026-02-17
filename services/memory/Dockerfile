FROM python:3.11-slim
WORKDIR /app
COPY services/memory/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ /app/common/
COPY services/memory/memory_service.py .
EXPOSE 8300
CMD ["python", "-m", "uvicorn", "memory_service:app", "--host", "0.0.0.0", "--port", "8300"]
