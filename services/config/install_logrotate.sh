#!/bin/bash
# Install logrotate config for SecureBot
# Run once: sudo bash install_logrotate.sh

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Please run as root (use sudo)"
    exit 1
fi

LOGROTATE_DIR="/etc/logrotate.d"
CONFIG_FILE="/home/tasker0/securebot/services/config/securebot-logrotate"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

cp "$CONFIG_FILE" "$LOGROTATE_DIR/securebot"
chmod 644 "$LOGROTATE_DIR/securebot"

echo "✓ Logrotate config installed to $LOGROTATE_DIR/securebot"
echo "Test with: sudo logrotate -d /etc/logrotate.d/securebot"
