#!/bin/bash
# Hourly summary - runs via systemd timer

MEMORY_DIR="/home/tasker0/securebot/memory"
OLLAMA_URL="http://localhost:11434"
TIMESTAMP=$(date -Iseconds)
LOG_FILE="$MEMORY_DIR/hourly.log"

# Get system stats
CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
RAM=$(free -h | grep Mem | awk '{print $3"/"$2}')
DISK=$(df -h / | tail -1 | awk '{print $3"/"$2}')

echo "[$TIMESTAMP] Hourly Summary" >> "$LOG_FILE"
echo "CPU: $CPU% | RAM: $RAM | Disk: $DISK" >> "$LOG_FILE"

# Check Docker container health
cd /home/tasker0/securebot
CONTAINER_STATUS=$(docker compose ps --format json 2>/dev/null | jq -r '.[] | "\(.Service): \(.State)"' 2>/dev/null)
if [ -n "$CONTAINER_STATUS" ]; then
    echo "Containers: $CONTAINER_STATUS" >> "$LOG_FILE"
fi

# Log Ollama model status
if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    MODELS=$(curl -sf "$OLLAMA_URL/api/tags" | jq -r '.models[].name' | tr '\n' ', ' | sed 's/,$//')
    echo "Ollama models: $MODELS" >> "$LOG_FILE"
fi

echo "---" >> "$LOG_FILE"
