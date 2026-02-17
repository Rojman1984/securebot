#!/bin/bash
# SecureBot Heartbeat - runs via systemd timer
# Keeps Ollama warm and updates session context

MEMORY_DIR="/home/tasker0/securebot/memory"
LOG_FILE="$MEMORY_DIR/heartbeat.log"
OLLAMA_URL="http://localhost:11434"
MEMORY_SERVICE="http://localhost:8300"
TIMESTAMP=$(date -Iseconds)

log() {
    echo "[$TIMESTAMP] $1" >> "$LOG_FILE"
}

# 1. Keep Ollama warm
if curl -sf "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    log "Ollama: healthy"
    # Warm up with tiny prompt to prevent cold starts
    curl -sf -X POST "$OLLAMA_URL/api/generate" \
        -d '{"model":"phi4-mini:3.8b","prompt":"ping","stream":false}' \
        > /dev/null 2>&1
else
    log "WARNING: Ollama unreachable"
fi

# 2. Update session timestamp
if curl -sf "$MEMORY_SERVICE/health" > /dev/null 2>&1; then
    curl -sf -X POST "$MEMORY_SERVICE/memory/session" \
        -H "Content-Type: application/json" \
        -d "{\"last_active\": \"$TIMESTAMP\"}" > /dev/null 2>&1
    log "Memory service: updated"
else
    log "WARNING: Memory service unreachable"
fi

# 3. Check Docker services
for service in gateway vault; do
    if curl -sf "http://localhost:$([ "$service" = "gateway" ] && echo 8080 || echo 8200)/health" > /dev/null 2>&1; then
        log "$service: healthy"
    else
        log "WARNING: $service unreachable - attempting restart"
        cd /home/tasker0/securebot && docker compose restart $service
    fi
done

log "Heartbeat complete"
