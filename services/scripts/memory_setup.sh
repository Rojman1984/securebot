#!/bin/bash
# SecureBot Memory Setup Wizard
# Run once after cloning: bash services/scripts/memory_setup.sh

MEMORY_DIR="$(dirname "$0")/../../memory"
TEMPLATES_DIR="$MEMORY_DIR/templates"

echo "================================"
echo " SecureBot Memory Setup Wizard"
echo "================================"
echo ""

# Check if already set up
if [ -f "$MEMORY_DIR/user.md" ]; then
    read -p "Memory already configured. Reconfigure? (y/N): " reconfigure
    if [ "$reconfigure" != "y" ]; then
        echo "Keeping existing configuration."
        exit 0
    fi
fi

# Collect user info
read -p "Your name: " USER_NAME
read -p "GitHub username: " GITHUB_USER
read -p "Your role/job title: " USER_ROLE
read -p "Primary hardware (e.g. Mac Mini M4): " USER_HARDWARE
read -p "Ollama model (e.g. phi4-mini:3.8b): " OLLAMA_MODEL

# Create memory directory structure
mkdir -p "$MEMORY_DIR/archive"

# Copy and personalize soul.md
cp "$TEMPLATES_DIR/soul.template.md" "$MEMORY_DIR/soul.md"
sed -i "s/\[YOUR NAME\]/$USER_NAME/g" "$MEMORY_DIR/soul.md"
sed -i "s/\[YOUR_GITHUB\]/$GITHUB_USER/g" "$MEMORY_DIR/soul.md"

# Copy and personalize user.md
cp "$TEMPLATES_DIR/user.template.md" "$MEMORY_DIR/user.md"
sed -i "s/\[YOUR NAME\]/$USER_NAME/g" "$MEMORY_DIR/user.md"
sed -i "s/\[YOUR_GITHUB_USERNAME\]/$GITHUB_USER/g" "$MEMORY_DIR/user.md"
sed -i "s/\[YOUR CURRENT ROLE\]/$USER_ROLE/g" "$MEMORY_DIR/user.md"
sed -i "s/\[YOUR HARDWARE SPECS\]/$USER_HARDWARE/g" "$MEMORY_DIR/user.md"
sed -i "s/\[YOUR OLLAMA MODELS\]/$OLLAMA_MODEL/g" "$MEMORY_DIR/user.md"
sed -i "s/\[DATE\]/$(date +%Y-%m-%d)/g" "$MEMORY_DIR/user.md"

# Copy session and tasks templates
cp "$TEMPLATES_DIR/session.template.md" "$MEMORY_DIR/session.md"
cp "$TEMPLATES_DIR/tasks.template.json" "$MEMORY_DIR/tasks.json"

# Set permissions
chmod 444 "$MEMORY_DIR/soul.md"  # Read-only!
chmod 644 "$MEMORY_DIR/user.md"
chmod 644 "$MEMORY_DIR/session.md"
chmod 644 "$MEMORY_DIR/tasks.json"

echo ""
echo "✅ Memory system configured!"
echo ""
echo "Files created:"
echo "  memory/soul.md    (read-only - agent identity)"
echo "  memory/user.md    (your profile)"
echo "  memory/session.md (session context)"
echo "  memory/tasks.json (task list)"
echo ""

# Embed memory files into ChromaDB (after docker-compose up)
echo "Waiting for RAG service to be ready..."
sleep 10

if curl -s -f http://localhost:8400/health > /dev/null 2>&1; then
    echo "Embedding memory files into ChromaDB..."
    if curl -s -X POST http://localhost:8400/embed/memory | grep -q '"status":"ok"'; then
        echo "✅ Memory embedded into ChromaDB"
    else
        echo "⚠️  Warning: Memory embedding failed (run services/scripts/embed_memory.sh manually)"
    fi
else
    echo "⚠️  Warning: RAG service not available yet"
    echo "    After starting docker-compose, run: services/scripts/embed_memory.sh"
fi

echo ""
echo "Edit these files to personalize:"
echo "  nano memory/user.md"
echo ""
echo "To make soul.md editable temporarily:"
echo "  chmod 644 memory/soul.md"
echo "  nano memory/soul.md"
echo "  chmod 444 memory/soul.md"
