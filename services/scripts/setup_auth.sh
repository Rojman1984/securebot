#!/bin/bash
#
# SecureBot - Service Authentication Setup
#
# Generates shared HMAC secret for inter-service authentication.
# Run this once during initial setup.
#

set -e

PROJECT_ROOT="/home/tasker0/securebot"
ENV_FILE="${PROJECT_ROOT}/.env"

echo "════════════════════════════════════════════════"
echo "SecureBot - Service Authentication Setup"
echo "════════════════════════════════════════════════"
echo ""

# Generate strong shared secret (64 hex characters = 256 bits)
echo "🔐 Generating HMAC shared secret..."
SERVICE_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")

echo "✅ Generated secret: ${SERVICE_SECRET:0:16}... (truncated for security)"
echo ""

# Check if .env already exists
if [ -f "$ENV_FILE" ]; then
    echo "⚠️  WARNING: .env file already exists!"
    echo "Current contents:"
    cat "$ENV_FILE"
    echo ""
    read -p "Overwrite? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Aborted. No changes made."
        exit 1
    fi
fi

# Create .env file
echo "📝 Creating .env file..."
cat > "$ENV_FILE" << ENVEOF
# SecureBot Service Authentication
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# DO NOT COMMIT THIS FILE - it contains secrets!

# Shared HMAC secret for inter-service authentication
# All services use this to sign and verify requests
SERVICE_SECRET=$SERVICE_SECRET

# Vault master password
# Change this in production!
VAULT_PASSWORD=change-me-in-production

# Add other secrets as needed:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
ENVEOF

chmod 600 "$ENV_FILE"

echo "✅ .env file created with restricted permissions (600)"
echo ""

# Verify .gitignore
if ! grep -q "^\.env$" "${PROJECT_ROOT}/.gitignore" 2>/dev/null; then
    echo "⚠️  WARNING: .env not in .gitignore!"
    echo "Adding .env to .gitignore for safety..."
    echo ".env" >> "${PROJECT_ROOT}/.gitignore"
fi

echo "════════════════════════════════════════════════"
echo "✅ Service authentication configured!"
echo "════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Review/update .env file if needed"
echo "  2. Update VAULT_PASSWORD in .env"
echo "  3. Add API keys (OPENAI_API_KEY, etc.) to .env"
echo "  4. Run: docker compose up -d"
echo ""
echo "Security notes:"
echo "  • .env file is gitignored (never commit it!)"
echo "  • Secret is shared by all services"
echo "  • Services authenticate using HMAC-SHA256"
echo "  • 30-second timestamp window for replay prevention"
echo ""
