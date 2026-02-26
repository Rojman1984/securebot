FROM python:3.11-slim

# Install OS dependencies: Node.js (for Pi CLI), shellcheck, jq, curl, sudo
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    shellcheck \
    jq \
    sudo \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Pi CLI globally
RUN npm install -g @mariozechner/pi-coding-agent

# Install Python dependencies
# torch CPU-only — CodeBot does not need GPU (gateway owns the GPU)
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    httpx \
    pyyaml \
    flake8 \
    gliclass \
    transformers \
    "torch==2.2.2+cpu" \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Create non-root user — CodeBot MUST NOT run as root
RUN groupadd -r codebot-worker \
    && useradd -r -g codebot-worker -m -d /workspace codebot-worker

WORKDIR /workspace

# Copy service files (build context is project root)
COPY codebot/codebot_service.py /workspace/codebot_service.py
COPY codebot/skill_router.py /workspace/skill_router.py
COPY codebot/pi_config.json /workspace/pi_config.json
COPY codebot/tools/ /workspace/tools/

# Make shell tools executable
RUN chmod +x /workspace/tools/tool_lint_bash.sh \
    && chmod +x /workspace/tools/tool_lint_python.sh \
    && chmod +x /workspace/tools/tool_commit_skill.sh

# Own workspace as codebot-worker
RUN chown -R codebot-worker:codebot-worker /workspace

USER codebot-worker

EXPOSE 8500

CMD ["python3", "-m", "uvicorn", "codebot_service:app", "--host", "0.0.0.0", "--port", "8500"]
