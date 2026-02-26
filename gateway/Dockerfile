FROM python:3.11-slim

WORKDIR /app

# Install sudo and bash; create locked-down skill execution user
RUN apt-get update && apt-get install -y --no-install-recommends sudo && \
    rm -rf /var/lib/apt/lists/* && \
    useradd -u 1000 -m appuser && \
    useradd -r -s /bin/bash -m securebot-scripts && \
    passwd -l securebot-scripts && \
    echo "appuser ALL=(securebot-scripts) NOPASSWD: /bin/bash, /usr/local/bin/python3, /usr/bin/systemctl, /usr/bin/journalctl" > /etc/sudoers.d/securebot-scripts && \
    chmod 440 /etc/sudoers.d/securebot-scripts

# Install PyTorch with CUDA 12.1 support before other deps
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --timeout 300

# Copy requirements
COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common library
COPY common/ /app/common/

# Copy application files
COPY gateway/gateway_service.py .
COPY gateway/orchestrator.py .
COPY gateway/gliclass_classifier.py .
COPY gateway/watchdog_service.py .

EXPOSE 8080

CMD ["python", "gateway_service.py"]
