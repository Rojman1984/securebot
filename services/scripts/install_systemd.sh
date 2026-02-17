#!/bin/bash
# Install SecureBot systemd units
# Run once: sudo bash install_systemd.sh

SYSTEMD_DIR="/etc/systemd/system"
SCRIPTS_DIR="/home/tasker0/securebot/services/scripts"
UNITS_DIR="/home/tasker0/securebot/services/systemd"

echo "==================================="
echo "SecureBot systemd Unit Installer"
echo "==================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

# Verify directories exist
if [ ! -d "$UNITS_DIR" ]; then
    echo "ERROR: Units directory not found: $UNITS_DIR"
    exit 1
fi

if [ ! -d "$SCRIPTS_DIR" ]; then
    echo "ERROR: Scripts directory not found: $SCRIPTS_DIR"
    exit 1
fi

echo "Step 1: Installing Ollama embedding model..."
if command -v ollama &> /dev/null; then
    echo "  Pulling nomic-embed-text model..."
    su - tasker0 -c "ollama pull nomic-embed-text" || echo "  Warning: Could not pull embedding model"
    echo "✓ Embedding model installed"
else
    echo "  Warning: Ollama not found, skipping model installation"
fi
echo ""

echo "Step 2: Making scripts executable..."
chmod +x "$SCRIPTS_DIR"/*.sh
echo "✓ Scripts are now executable"
echo ""

echo "Step 2: Copying systemd units to $SYSTEMD_DIR..."
cp "$UNITS_DIR"/*.service "$SYSTEMD_DIR/"
cp "$UNITS_DIR"/*.timer "$SYSTEMD_DIR/"
echo "✓ Units copied"
echo ""

echo "Step 3: Reloading systemd daemon..."
systemctl daemon-reload
echo "✓ Systemd reloaded"
echo ""

echo "Step 4: Enabling and starting services..."
echo "  - Memory service..."
systemctl enable --now securebot-memory.service 2>/dev/null || echo "  (will start when docker-compose is ready)"

echo "  - Heartbeat timer (every 5 minutes)..."
systemctl enable --now securebot-heartbeat.timer

echo "  - Hourly summary timer..."
systemctl enable --now securebot-hourly.timer

echo "  - Daily report timer..."
systemctl enable --now securebot-daily.timer

echo "✓ All timers enabled and started"
echo ""

echo "==================================="
echo "Installation Complete!"
echo "==================================="
echo ""
echo "Check status with:"
echo "  systemctl status securebot-heartbeat.timer"
echo "  systemctl status securebot-hourly.timer"
echo "  systemctl status securebot-daily.timer"
echo ""
echo "View logs with:"
echo "  tail -f /home/tasker0/securebot/memory/heartbeat.log"
echo "  tail -f /home/tasker0/securebot/memory/hourly.log"
echo "  tail -f /home/tasker0/securebot/memory/daily.log"
echo ""
echo "List all timers:"
echo "  systemctl list-timers securebot-*"
echo ""
