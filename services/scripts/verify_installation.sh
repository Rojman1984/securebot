#!/bin/bash
# SecureBot Installation Verification
# Checks all components and reports status

echo "═══════════════════════════════════════════"
echo "  SecureBot Installation Verification"
echo "═══════════════════════════════════════════"
echo ""

ERRORS=0
WARNINGS=0

check_service() {
    SERVICE=$1
    PORT=$2
    NAME=$3

    if curl -sf "http://localhost:$PORT/health" > /dev/null 2>&1; then
        echo "✓ $NAME (port $PORT): healthy"
    else
        echo "✗ $NAME (port $PORT): FAILED"
        ((ERRORS++))
    fi
}

check_systemd_timer() {
    TIMER=$1
    if systemctl is-active --quiet "$TIMER"; then
        echo "✓ $TIMER: active"
    else
        echo "⚠ $TIMER: inactive (run install_systemd.sh)"
        ((WARNINGS++))
    fi
}

check_file() {
    FILE=$1
    NAME=$2
    if [ -f "$FILE" ]; then
        echo "✓ $NAME: exists"
    else
        echo "✗ $NAME: MISSING"
        ((ERRORS++))
    fi
}

echo "1. Docker Services"
echo "───────────────────"
check_service "gateway" "8080" "Gateway"
check_service "vault" "8200" "Vault"
check_service "memory-service" "8300" "Memory Service"
echo ""

echo "2. Ollama"
echo "─────────"
if curl -sf "http://localhost:11434/api/tags" > /dev/null 2>&1; then
    echo "✓ Ollama: running"
    MODELS=$(curl -s "http://localhost:11434/api/tags" | jq -r '.models[].name' | tr '\n' ', ' | sed 's/,$//')
    echo "  Models: $MODELS"
else
    echo "✗ Ollama: NOT RUNNING"
    ((ERRORS++))
fi
echo ""

echo "3. Memory Files"
echo "───────────────"
check_file "/home/tasker0/securebot/memory/soul.md" "soul.md"
check_file "/home/tasker0/securebot/memory/user.md" "user.md"
check_file "/home/tasker0/securebot/memory/session.md" "session.md"
check_file "/home/tasker0/securebot/memory/tasks.json" "tasks.json"
echo ""

echo "4. Systemd Timers (optional)"
echo "────────────────────────────"
check_systemd_timer "securebot-heartbeat.timer"
check_systemd_timer "securebot-hourly.timer"
check_systemd_timer "securebot-daily.timer"
echo ""

echo "5. Automation Skills"
echo "────────────────────"
check_file "/home/tasker0/securebot/skills/cron-manager/SKILL.md" "cron-manager"
check_file "/home/tasker0/securebot/skills/systemd-service/SKILL.md" "systemd-service"
check_file "/home/tasker0/securebot/skills/systemd-timer/SKILL.md" "systemd-timer"
check_file "/home/tasker0/securebot/skills/bash-automation/SKILL.md" "bash-automation"
check_file "/home/tasker0/securebot/skills/ansible-playbook/SKILL.md" "ansible-playbook"
echo ""

echo "6. Search Skills"
echo "────────────────"
check_file "/home/tasker0/securebot/skills/search-google/SKILL.md" "search-google"
check_file "/home/tasker0/securebot/skills/search-tavily/SKILL.md" "search-tavily"
check_file "/home/tasker0/securebot/skills/search-duckduckgo/SKILL.md" "search-duckduckgo"
echo ""

echo "═══════════════════════════════════════════"
echo "  Summary"
echo "═══════════════════════════════════════════"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo "✓ All checks passed! SecureBot is ready."
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo "⚠ $WARNINGS warnings (optional features not enabled)"
    echo ""
    echo "To enable systemd timers:"
    echo "  sudo bash /home/tasker0/securebot/services/scripts/install_systemd.sh"
    exit 0
else
    echo "✗ $ERRORS errors, $WARNINGS warnings"
    echo ""
    echo "Please fix errors before using SecureBot."
    exit 1
fi
