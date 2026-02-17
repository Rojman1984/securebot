FROM python:3.11-slim
WORKDIR /app
COPY services/rag/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common/ /app/common/
COPY services/rag/rag_service.py .
EXPOSE 8400
CMD ["python", "rag_service.py"]
