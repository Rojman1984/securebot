# SecureBot Quick Start Guide

## Prerequisites Check

```bash
# Check Docker
docker --version

# Check Docker Compose
docker compose version

# Check Ollama
ollama --version

# Check if Ollama is running
curl http://localhost:11434/api/tags
```

## Installation (5 Minutes)

### 1. Pull Ollama Model

```bash
# Budget hardware (8GB RAM)
ollama pull phi4-mini:3.8b

# OR Mid-range (16GB RAM)
ollama pull llama3:8b

# OR Mac Mini M4 / AMD Ryzen AI Max (32GB+ RAM)
ollama pull llama3:70b
```

### 2. Configure Secrets

```bash
mkdir -p vault/secrets
nano vault/secrets/secrets.json
```

Paste this and add your API keys:

```json
{
  "anthropic_api_key": "your-anthropic-api-key-here",
  "search": {
    "google_api_key": "optional-google-api-key",
    "google_cx": "optional-google-cx",
    "tavily_api_key": "optional-tavily-api-key"
  }
}
```

**Note:** Only `anthropic_api_key` is required. Search providers are optional.

### 3. Start Services

```bash
docker compose up -d
```

### 4. Verify Installation

```bash
bash services/scripts/verify_installation.sh
```

### 5. (Optional) Install System Automation

```bash
# Install systemd timers for heartbeat
sudo bash services/scripts/install_systemd.sh

# Install log rotation
sudo bash services/config/install_logrotate.sh
```

## First Test

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "test",
    "text": "Hello! What can you help me with?"
  }'
```

## Common Commands

### Check Service Health

```bash
# All services
curl http://localhost:8080/health  # Gateway
curl http://localhost:8200/health  # Vault
curl http://localhost:8300/health  # Memory
curl http://localhost:11434/api/tags  # Ollama

# Docker status
docker compose ps
```

### View Logs

```bash
# All logs
docker compose logs -f

# Specific service
docker compose logs -f gateway
docker compose logs -f vault
docker compose logs -f memory-service

# Memory system logs
tail -f memory/heartbeat.log
tail -f memory/hourly.log
tail -f memory/daily.log
```

### Restart Services

```bash
# Restart all
docker compose restart

# Restart specific service
docker compose restart gateway
docker compose restart memory-service
```

### Check Memory Context

```bash
# View soul (identity)
curl http://localhost:8300/memory/soul

# View user profile
curl http://localhost:8300/memory/user

# View current session
curl http://localhost:8300/memory/session

# Get combined context
curl http://localhost:8300/memory/context

# Get tasks
curl http://localhost:8300/tasks
```

### Check System Automation (if installed)

```bash
# List timers
systemctl list-timers securebot-*

# Check specific timer
systemctl status securebot-heartbeat.timer

# View timer logs
journalctl -u securebot-heartbeat.service -n 50
```

## Usage Examples

### Simple Question (Free - Ollama)

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user1",
    "text": "Explain Python decorators"
  }'
```

### Web Search (Free - Uses search providers)

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user1",
    "text": "What are the latest AI developments?"
  }'
```

### Complex Query (Paid - Uses Claude API ~$0.006)

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user1",
    "text": "Design a microservices architecture for an e-commerce platform. Consider scalability, fault tolerance, and data consistency."
  }'
```

### Use Automation Skill

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user1",
    "text": "How do I schedule a backup script to run daily at 2am using cron?"
  }'
```

## Troubleshooting

### Gateway won't start

```bash
# Check if port 8080 is in use
sudo lsof -i :8080

# View gateway logs
docker compose logs gateway
```

### Ollama connection failed

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Check if model is pulled
ollama list
```

### Memory service unhealthy

```bash
# Check memory service logs
docker compose logs memory-service

# Verify memory files exist
ls -la memory/

# Restart memory service
docker compose restart memory-service
```

### No response from AI

```bash
# Check if model is loaded in Ollama
ollama ps

# Check gateway can reach Ollama
docker compose exec gateway curl http://host.docker.internal:11434/api/tags

# View orchestrator logs
docker compose logs gateway | grep orchestrator
```

## Next Steps

1. **Read Documentation**
   - `docs/MEMORY.md` - Memory system and automation philosophy
   - `docs/ARCHITECTURE.md` - Technical architecture details
   - `docs/SKILLS.md` - How to create your own skills

2. **Explore Skills**
   - Browse `skills/` directory
   - Try automation skills (cron-manager, systemd-service, etc.)
   - Create your own skills for repetitive tasks

3. **Monitor System**
   - Check heartbeat logs regularly
   - Review hourly/daily summaries
   - Track Claude API usage and costs

4. **Customize**
   - Update `memory/user.md` with your preferences
   - Configure `~/.securebot/config.yml` for skill priorities
   - Adjust model in `docker-compose.yml` based on hardware

## Getting Help

- **Documentation:** `docs/` directory
- **Verify Installation:** `bash services/scripts/verify_installation.sh`
- **Check Logs:** `docker compose logs -f`
- **GitHub Issues:** Report bugs and request features

## Cost Tracking

SecureBot aims for $3-5/month. Track your usage:

```bash
# View search usage statistics
curl http://localhost:8200/search/usage

# Check daily summaries for API costs
tail -f memory/daily.log
```

**Remember:**
- Ollama queries = FREE
- Search queries = FREE (within tier limits)
- Skill execution = FREE
- Skill creation = ~$0.10 (one-time)
- Complex Claude queries = ~$0.006

Most queries should be FREE!
