# 🤖 SecureBot

> **Cost-Optimized AI Assistant with Hybrid Architecture**
> Self-hosted • Skill-Based • $3-5/month vs $97/month alternatives

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://www.docker.com/)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-green.svg)](https://www.python.org/)

---

## 🎯 What is SecureBot?

**SecureBot** is a cost-optimized, self-hosted AI assistant that combines the best of both worlds:
- 🏠 **Local inference** with Ollama (ANY model you want - runs on YOUR hardware)
- ☁️ **Cloud power** with Claude API (only for complex tasks and skill creation)
- 💰 **97% cost savings** - $3-5/month instead of $97/month
- 🔄 **Skill-based architecture** - Create once with Claude, reuse forever FREE with local models

Created by **Roland (Rojman1984)** • Built with AI assistance

---

## ✨ Key Features

- 🎛️ **Hardware Flexibility** - Works on ANY machine from budget laptops to GPU servers
- 💸 **Extreme Cost Efficiency** - Skills created with Claude API run FREE locally forever
- 🔒 **Security First** - Secrets isolated in vault, never exposed to AI models
- 🔍 **Multi-Provider Search** - Google Custom Search, Tavily, DuckDuckGo with auto-fallback
- 🧩 **Reusable Skills** - Create AI capabilities once, use infinitely at zero marginal cost
- 📊 **Zero-Shot Routing** - GLiClass (144M params, <50ms) routes by intent: search, task, knowledge, chat, or action — no heuristics, no scoring
- 🧠 **Memory & Continuity** - Persistent context across sessions with system-native automation
- 🤖 **System-Native Heartbeat** - systemd timers (not Python loops) for reliability
- ⚙️ **Automation Skills** - Teach cron, systemd, bash, and ansible best practices
- 🐳 **Docker-Native** - Simple deployment with docker-compose
- 🌐 **Multi-Channel Ready** - API endpoints for Telegram, Discord, CLI, or custom integrations

---

## 🖥️ Hardware Flexibility

**The faster your hardware, the faster your responses - but SecureBot works on ANY machine!**

SecureBot uses Ollama for local inference, which means YOU choose the model based on YOUR hardware:

| Hardware              | Recommended Model  | Response Speed | Monthly Cost |
|-----------------------|--------------------|----------------|--------------|
| 💻 Budget (8GB RAM)   | phi4-mini:3.8b     | ~50 seconds    | $0           |
| 🖥️ Mid (16GB RAM)     | llama3:8b          | ~30 seconds    | $0           |
| 🔥 **AMD Ryzen AI Max** | **llama3:70b**   | **~5 seconds** | **$0**       |
| 🍎 **Mac Mini M4**    | **llama3:70b**     | **~3 seconds** | **$0**       |
| 🚀 Mac Studio M4 Max  | llama3:405b        | ~5 seconds     | $0           |
| ⚡ GPU Server         | Any model          | <1 second      | $0           |

**Recommended Sweet Spots:**
- 🏆 **Mac Mini M4** ($599) - Best price/performance for Apple Silicon
- 🏆 **AMD Ryzen AI Max** - Best for Windows/Linux with integrated NPU + large iGPU
- 💼 **Budget Start** - Begin with phi4-mini on ANY machine, upgrade hardware later
- 🏢 **Enterprise** - Add GPU server for sub-second responses

**Key Point:** Claude API handles complex tasks (skill creation, architecture decisions) regardless of your local hardware. Your local model only handles simple execution and search summarization.

See [docs/HARDWARE.md](docs/HARDWARE.md) for detailed setup guides and benchmarks.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    GATEWAY (Port 8080)                          │
│  • Multi-channel message routing (Telegram/Discord/API)         │
│  • Search detection and orchestration                           │
│  • Memory context loading (soul/user/session)                   │
│  • Request/response formatting                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│ MEMORY SERVICE (8300)    │      │   VAULT (Port 8200)      │
│  • soul.md (identity)    │      │  • Secrets isolation     │
│  • user.md (profile)     │      │  • API key injection     │
│  • session.md (context)  │      │  • Search providers:     │
│  • tasks.json (todos)    │      │    - Google (100/day)    │
│  • REST API for files    │      │    - Tavily (1000/mo)    │
└──────────────────────────┘      │    - DuckDuckGo (free)   │
            │                     └──────────────────────────┘
            └─────────────────┬───────────────────┘
                              ▼
                              │
            ┌─────────────────┴─────────────────┐
            ▼                                   ▼
┌──────────────────────────┐      ┌──────────────────────────┐
│   VAULT (Port 8200)      │      │  OLLAMA (Port 11434)     │
│  • Secrets isolation     │      │  • Local inference       │
│  • API key injection     │      │  • ANY model YOU choose  │
│  • Search providers:     │      │  • Zero marginal cost    │
│    - Google (100/day)    │      │  • Speed = YOUR hardware │
│    - Tavily (1000/mo)    │      │  • phi4-mini (default)   │
│    - DuckDuckGo (free)   │      │  • llama3:8b             │
└──────────────────────────┘      │  • llama3:70b            │
            │                     │  • llama3:405b           │
            ▼                     │  • Custom models         │
┌──────────────────────────┐      └──────────────────────────┘
│  CLAUDE API (On-Demand)  │                  │
│  • Skill creation ($$$)  │                  │
│  • Complex reasoning     │                  │
│  • Architecture design   │                  │
│  • ~$0.006 per query     │                  │
└──────────────────────────┘                  │
            │                                 │
            └─────────────┬───────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│              ORCHESTRATOR (Zero-Shot Routing)                   │
│                                                                 │
│  [1] GLiClass Classification (144M params · <50ms)             │
│      │                                                          │
│      ├── search    → Vault Web Search → Ollama summary (FREE)  │
│      ├── task      → Memory tasks.json → Ollama summary (FREE) │
│      ├── knowledge → ChromaDB RAG context → Ollama (FREE)      │
│      ├── chat      → ChromaDB RAG context → Ollama (FREE)      │
│      └── action    → [2] SkillRegistry (deterministic match)   │
│                           ├── Match  → Execute locally (FREE)  │
│                           └── No match → [3] Haiku creates     │
│                                          skill → Execute (~$0.01│
│                                          one-time)              │
└─────────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SKILLS DIRECTORY                              │
│  • SKILL.md format (Claude Code compatible)                     │
│  • Reusable AI capabilities                                     │
│  • Created once ($$$), execute forever (FREE)                   │
│  • Categories: search, code, stt, tts, general                  │
└─────────────────────────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical deep dive.

---

## 💰 Cost Comparison

| Service           | Monthly Cost | Features                          |
|-------------------|--------------|-----------------------------------|
| **SecureBot**     | **$3-5**     | Self-hosted, unlimited local use  |
| Claude AI Pro     | $97          | Web interface, limited features   |
| ChatGPT Plus      | $20          | Web interface, rate limited       |
| Anthropic API     | ~$50-200     | Pay-per-token, no optimization    |

**How SecureBot Achieves 97% Savings:**

1. **Local Inference** - Ollama runs on YOUR hardware (zero marginal cost)
2. **Skill Reuse** - Create skill once with Claude ($0.10), execute unlimited times FREE
3. **Zero-Shot Routing** - GLiClass intent classification routes all queries to the optimal free local path; cloud API used only for new skill creation
4. **Free Search Tiers** - Google (100/day), Tavily (1000/mo), DuckDuckGo (unlimited)
5. **Secrets Management** - No accidental API calls leaking credentials

**Example Month:**
- 300 simple queries → Ollama → $0
- 20 search queries → Free tiers → $0
- 5 new skills created → Claude API → $0.50
- 10 complex queries → Claude API → $0.06
- **Total: ~$0.56** (vs $97 for Claude Pro)

See [docs/COST_ANALYSIS.md](docs/COST_ANALYSIS.md) for detailed breakdown.

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- Docker & Docker Compose
- Ollama installed and running
- 8GB+ RAM minimum (16GB+ recommended)
- Anthropic API key (for skill creation)

### Installation

```bash
# 1. Install Docker (if not already installed)
# Linux: https://docs.docker.com/engine/install/
# Mac: https://docs.docker.com/desktop/install/mac-install/
# Windows: https://docs.docker.com/desktop/install/windows-install/

# 2. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 3. Pull a model (choose based on your hardware)
# Budget (8GB RAM):
ollama pull phi4-mini:3.8b

# Mid-range (16GB RAM):
ollama pull llama3:8b

# Mac Mini M4 or AMD Ryzen AI Max (32GB+ RAM):
ollama pull llama3:70b

# High-end (64GB+ RAM):
ollama pull llama3:405b

# 4. Clone SecureBot
git clone https://github.com/Rojman1984/securebot.git
cd securebot

# 5. Configure secrets
mkdir -p vault/secrets
cat > vault/secrets/secrets.json << 'EOF'
{
  "anthropic_api_key": "your-anthropic-api-key-here",
  "search": {
    "google_api_key": "your-google-api-key-optional",
    "google_cx": "your-google-cx-optional",
    "tavily_api_key": "your-tavily-api-key-optional"
  }
}
EOF

# 6. (OPTIONAL) Update model in docker-compose.yml
# Edit line 31: OLLAMA_MODEL=phi4-mini:3.8b
# Change to your preferred model (llama3:8b, llama3:70b, etc.)

# 7. Start services
docker-compose up -d

# 8. Install system automation (optional but recommended)
sudo bash services/scripts/install_systemd.sh
sudo bash services/config/install_logrotate.sh

# 9. Verify installation
curl http://localhost:8080/health
curl http://localhost:8200/health
curl http://localhost:8300/health  # Memory service

# 10. Send your first message!
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "test-user",
    "text": "What is the capital of France?"
  }'
```

**Memory & Automation Setup:**
- Memory system provides persistent context across sessions
- Heartbeat keeps Ollama warm and checks service health (every 5 min)
- Hourly summaries track system stats
- Daily reports archive sessions and task status
- See [docs/MEMORY.md](docs/MEMORY.md) for details

**Response times:**
- Budget hardware (phi4-mini): 30-50 seconds
- Mid-range (llama3:8b): 15-30 seconds
- Mac Mini M4 (llama3:70b): 3-5 seconds
- GPU server: <1 second

See [docs/INSTALL.md](docs/INSTALL.md) for detailed installation guide.

---

## 📖 Configuration

### Secrets (vault/secrets/secrets.json)

```json
{
  "anthropic_api_key": "sk-ant-...",
  "search": {
    "google_api_key": "AIza...",
    "google_cx": "custom-search-engine-id",
    "tavily_api_key": "tvly-..."
  }
}
```

### User Config (~/.securebot/config.yml)

```yaml
skills:
  enabled:
    - search-google
    - search-tavily
    - search-duckduckgo

  priorities:
    search-google: 1      # Try Google first
    search-tavily: 2      # Then Tavily
    search-duckduckgo: 3  # DuckDuckGo as fallback

  rate_limits:
    google:
      daily: 100
      monthly: 3000
    tavily:
      monthly: 1000

gateway:
  search_detection: normal  # strict, normal, relaxed
```

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for complete reference.

---

## 💡 Usage Examples

### Simple Query (Uses Ollama - FREE)

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user123",
    "text": "Explain Python list comprehensions"
  }'
```

### Search Query (Multi-Provider)

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user123",
    "text": "What are the latest AI developments in 2026?"
  }'
```

### Complex Query (Uses Claude API - ~$0.006)

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user123",
    "text": "Design a scalable microservices architecture for an e-commerce platform with high availability requirements. Consider trade-offs between consistency and availability."
  }'
```

### Skill Creation (One-time cost ~$0.10)

```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "user123",
    "text": "Create a skill to analyze Python code for security vulnerabilities"
  }'
```

After creation, the skill runs FREE on Ollama forever!

---

## 🧩 Skills System

**Skills are reusable AI capabilities** - the secret sauce of SecureBot's cost efficiency.

### How Skills Work

1. **One-Time Creation** - Claude API analyzes your request and creates a SKILL.md file (~$0.10)
2. **Infinite Reuse** - Skill executes with local Ollama model (FREE forever)
3. **Zero Marginal Cost** - Each execution costs $0 after initial skill creation

### Example Skill Structure

```markdown
---
name: python-security-audit
description: Analyze Python code for common security vulnerabilities including SQL injection, XSS, command injection, and insecure deserialization
category: code
priority: 1
---

# Python Security Audit

Perform comprehensive security analysis on Python code.

## Steps

1. Analyze code for SQL injection vulnerabilities
2. Check for XSS attack vectors
3. Identify command injection risks
4. Review deserialization security
5. Flag hardcoded credentials
6. Assess input validation

## Output Format

- Severity: HIGH/MEDIUM/LOW
- Vulnerability type
- Location (file:line)
- Recommendation
```

### Built-in Skills

**Search Skills:**
- **search-google** - Google Custom Search (100 queries/day free)
- **search-tavily** - Tavily AI Search (1000 queries/month free)
- **search-duckduckgo** - DuckDuckGo Search (no API key needed)

**Automation Skills:**
- **cron-manager** - Schedule recurring tasks with cron
- **systemd-service** - Create background services
- **systemd-timer** - Modern alternative to cron
- **bash-automation** - System automation scripts
- **ansible-playbook** - Multi-machine automation

See [docs/SKILLS.md](docs/SKILLS.md) for creating your own skills.
See [docs/MEMORY.md](docs/MEMORY.md) for memory system and automation philosophy.

---

## 🛠️ Development

### Project Structure

```
securebot/
├── gateway/              # API gateway and message routing
│   ├── gateway_service.py   # FastAPI service
│   └── orchestrator.py      # Smart routing logic
├── vault/                # Secrets management
│   ├── vault_service.py     # Secure API key injection
│   └── secrets/             # secrets.json (gitignored)
├── skills/               # Reusable AI skills
│   ├── search-google/
│   ├── search-tavily/
│   └── search-duckduckgo/
├── common/               # Shared utilities
│   └── config.py            # Configuration management
├── docker-compose.yml    # Service orchestration
└── docs/                 # Documentation
```

### Tech Stack

- **Python 3.10+** - Core services
- **FastAPI** - REST API endpoints
- **Ollama** - Local LLM inference
- **Docker** - Containerization
- **Claude API** - Complex reasoning (on-demand)

### Developed On

- **Hardware:** Ryzen 5 3500U mini PC with 16GB RAM
- **Model:** phi4-mini:3.8b and llama3:8b
- **Performance:** 14-50 seconds per query (budget hardware proves it works!)
- **Assistance:** Built with Claude Code and Windsurf IDE

---

## 🤝 Contributing

We welcome contributions! SecureBot is built by the community, for the community.

### Ways to Contribute

1. **Skills** - Create and share reusable skills
2. **Providers** - Add new search providers (Brave, Perplexity, etc.)
3. **Integrations** - Build Telegram, Discord, Slack bots
4. **Documentation** - Improve guides and examples
5. **Bug Fixes** - Report and fix issues

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📊 Monitoring & Health

### Health Checks

```bash
# Gateway health
curl http://localhost:8080/health

# Vault health (shows configured providers)
curl http://localhost:8200/health

# Search usage statistics
curl http://localhost:8200/search/usage

# Ollama health
curl http://localhost:11434/api/tags
```

### Logs

```bash
# View all logs
docker-compose logs -f

# Gateway logs only
docker-compose logs -f gateway

# Vault logs only
docker-compose logs -f vault
```

---

## 🔐 Security

SecureBot implements **defense-in-depth security** with multiple layers:

### 🔒 Inter-Service Authentication

- **HMAC-SHA256 Signed Requests** - All service-to-service communication is cryptographically signed
- **Replay Attack Prevention** - 30-second timestamp window + nonce tracking
- **Service Trust Matrix** - Each service explicitly defines who can call it
- **Zero External Access** - External requests to internal services are rejected (401 Unauthorized)

### 🔑 Secret Management

- **Secrets Isolation** - API keys never exposed to AI models
- **Vault Pattern** - Secrets injected at execution time only
- **No Prompt Injection** - AI cannot access credentials via clever prompts
- **Environment Variables** - Secrets stored in `.env` (gitignored, never committed)

### 🌐 Network Security

- **Docker Network Isolation** - Services communicate on private `securebot` bridge network
- **Port Restrictions** - Only gateway (8080) exposed externally
- **Health Endpoints Public** - `/health` endpoints remain accessible for Docker healthchecks

### 🏠 Privacy

- **Local First** - Your data stays on your hardware
- **No Telemetry** - No analytics, tracking, or data collection
- **Your Models** - Use ANY Ollama model, hosted on YOUR machine

### 📚 Security Documentation

- **Full Security Model:** See [docs/SECURITY.md](docs/SECURITY.md)
- **Setup Guide:** Run `bash services/scripts/setup_auth.sh`
- **Trust Matrix:** Details which services can communicate
- **Troubleshooting:** Common auth issues and solutions

### 🛡️ What This Protects Against

✅ Unauthorized access to internal services
✅ Replay attacks (duplicate/old requests)
✅ Man-in-the-middle tampering
✅ Service impersonation
✅ Prompt injection credential theft
✅ External API abuse

**Note:** For production deployments requiring maximum security, consider implementing mTLS (mutual TLS) with client certificates. Contact for implementation guidance.

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

**Free to use, modify, and distribute.** Commercial use allowed.

---

## 🙏 Credits

- **Creator:** Roland (Rojman1984)
- **Built with:** Claude Code, Windsurf IDE
- **Inspired by:** The need for affordable, powerful AI assistants
- **Community:** Thank you to all contributors!

---

## 🔗 Links

- **GitHub:** https://github.com/Rojman1984/securebot
- **Issues:** https://github.com/Rojman1984/securebot/issues
- **Discussions:** https://github.com/Rojman1984/securebot/discussions

---

## 📣 Support

- ⭐ **Star this repo** if you find it useful!
- 🐛 **Report bugs** via GitHub Issues
- 💡 **Request features** via GitHub Discussions
- 📖 **Improve docs** via Pull Requests

---

**Built with ❤️ by the open-source community**

*Self-hosted • Cost-Optimized • Privacy-Focused • Community-Driven*
