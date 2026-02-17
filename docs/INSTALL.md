# 📦 Installation Guide

Complete step-by-step guide to installing SecureBot on any system.

---

## 📋 Table of Contents

- [System Requirements](#system-requirements)
- [Hardware Recommendations](#hardware-recommendations)
- [Step-by-Step Installation](#step-by-step-installation)
- [Configuration](#configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [GPU Acceleration](#gpu-acceleration)
- [Upgrading](#upgrading)

---

## 📋 System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| **OS** | Linux, macOS, Windows (with WSL2) |
| **RAM** | 8GB minimum (16GB+ recommended) |
| **Storage** | 10GB free space for models |
| **Docker** | Docker 20.10+ & Docker Compose 2.0+ |
| **Ollama** | Latest version |
| **Network** | Internet connection for API calls |

### Software Prerequisites

- **Docker & Docker Compose** - Container runtime
- **Ollama** - Local LLM inference
- **curl** - Testing API endpoints (usually pre-installed)
- **git** - Cloning repository

---

## 🖥️ Hardware Recommendations

SecureBot works on ANY hardware - choose your model based on your machine:

### 💰 Budget Tier (8-16GB RAM)

**Best For:** Getting started, testing, development

| Hardware | Example Devices | Recommended Model | Response Time |
|----------|-----------------|-------------------|---------------|
| 8GB RAM | Budget laptops, old PCs | phi4-mini:3.8b | ~50 seconds |
| 16GB RAM | Mid-range laptops | llama3:8b | ~30 seconds |

**Cost:** Hardware you already own + $0/month

```bash
# Budget setup
ollama pull phi4-mini:3.8b
```

---

### 🔥 Recommended Tier (32GB+ RAM)

**Best For:** Daily use, production, excellent performance

#### 🏆 Mac Mini M4 ($599)

**Why Recommended:**
- ✅ Best price/performance for Apple Silicon
- ✅ Unified memory architecture (32GB+ shared between CPU/GPU)
- ✅ Metal acceleration (built-in)
- ✅ Low power consumption
- ✅ Silent operation
- ✅ Great resale value

**Performance:**
- llama3:70b: ~3 seconds per query
- llama3:405b: ~8 seconds per query (64GB model)

**Setup:**
```bash
# Mac Mini M4 recommended setup
ollama pull llama3:70b

# For 64GB Mac Mini M4 Pro:
ollama pull llama3:405b
```

#### 🏆 AMD Ryzen AI Max (Windows/Linux)

**Why Recommended:**
- ✅ Best for Windows/Linux users
- ✅ Integrated NPU (AI accelerator)
- ✅ Large integrated GPU (up to 32GB shared memory)
- ✅ No discrete GPU needed
- ✅ DirectML acceleration
- ✅ More affordable than Intel equivalents

**Performance:**
- llama3:70b: ~5 seconds per query

**Setup:**
```bash
# AMD Ryzen AI Max recommended setup
ollama pull llama3:70b

# Enable NPU acceleration (Windows)
# See GPU Acceleration section below
```

**Cost:** $599-1299 (one-time) + $0/month

---

### 🚀 High-Performance Tier (64GB+ RAM or Dedicated GPU)

**Best For:** Enterprise, power users, sub-second responses

| Hardware | Models Supported | Response Time |
|----------|------------------|---------------|
| Mac Studio M4 Max (64GB+) | llama3:405b | ~5 seconds |
| NVIDIA RTX 4090 | Any model | <1 second |
| AMD MI300X | Any model | <1 second |
| Server with 128GB+ RAM | llama3:405b | ~3 seconds |

**Setup:**
```bash
# High-performance setup
ollama pull llama3:405b

# Or use specialized models
ollama pull codellama:70b
ollama pull deepseek-coder:33b
```

**Cost:** $2000-5000 (one-time) + $0/month

---

### 🏢 Enterprise Tier (GPU Server)

**Best For:** Multiple users, production deployments, real-time responses

**Options:**
- Cloud GPU instances (RunPod, Lambda Labs)
- On-premises GPU server
- Kubernetes cluster with GPU nodes

**Performance:** <1 second for any model

**Setup:** See [GPU Acceleration](#gpu-acceleration) section

---

## 🚀 Step-by-Step Installation

### Step 1: Install Docker

#### Linux (Ubuntu/Debian)

```bash
# Remove old versions
sudo apt-get remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt-get update
sudo apt-get install -y \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

#### macOS

```bash
# Download Docker Desktop from:
# https://docs.docker.com/desktop/install/mac-install/

# Or use Homebrew:
brew install --cask docker

# Start Docker Desktop from Applications
# Verify installation:
docker --version
docker compose version
```

#### Windows (WSL2)

```bash
# 1. Install WSL2:
# https://docs.microsoft.com/en-us/windows/wsl/install

# 2. Download Docker Desktop from:
# https://docs.docker.com/desktop/install/windows-install/

# 3. Enable WSL2 integration in Docker Desktop settings

# 4. Verify in WSL2 terminal:
docker --version
docker compose version
```

---

### Step 2: Install Ollama

#### Linux

```bash
# One-line installation
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version

# Start Ollama service (if not auto-started)
ollama serve
```

#### macOS

```bash
# Download from https://ollama.com/download/mac

# Or use Homebrew:
brew install ollama

# Start Ollama
ollama serve
```

#### Windows (WSL2)

```bash
# In WSL2 terminal:
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama
ollama serve
```

---

### Step 3: Pull Your Model

**Choose based on your hardware from the table above:**

```bash
# Budget (8GB RAM) - Works on ANY machine
ollama pull phi4-mini:3.8b

# Mid-range (16GB RAM)
ollama pull llama3:8b

# Recommended (Mac Mini M4 / AMD Ryzen AI Max with 32GB+)
ollama pull llama3:70b

# High-end (Mac Studio / GPU server with 64GB+)
ollama pull llama3:405b

# Verify model is downloaded
ollama list
```

**Model sizes:**
- phi4-mini:3.8b → ~2.3GB download
- llama3:8b → ~4.7GB download
- llama3:70b → ~40GB download
- llama3:405b → ~231GB download

---

### Step 4: Clone SecureBot Repository

```bash
# Clone from GitHub
git clone https://github.com/Rojman1984/securebot.git
cd securebot

# Check directory structure
ls -la
```

---

### Step 5: Configure Secrets

Create the secrets file with your API keys:

```bash
# Create secrets directory
mkdir -p vault/secrets

# Create secrets.json
cat > vault/secrets/secrets.json << 'EOF'
{
  "anthropic_api_key": "sk-ant-api03-YOUR-API-KEY-HERE",
  "search": {
    "google_api_key": "YOUR-GOOGLE-API-KEY-OPTIONAL",
    "google_cx": "YOUR-GOOGLE-CUSTOM-SEARCH-ID-OPTIONAL",
    "tavily_api_key": "tvly-YOUR-TAVILY-KEY-OPTIONAL"
  }
}
EOF

# Secure the file
chmod 600 vault/secrets/secrets.json
```

#### Getting API Keys

**Anthropic API Key (Required for skill creation):**
1. Sign up at https://console.anthropic.com/
2. Navigate to API Keys section
3. Create new key
4. Copy `sk-ant-api03-...` key

**Google Custom Search (Optional - 100 queries/day free):**
1. Create project: https://console.cloud.google.com/
2. Enable Custom Search API
3. Create API key
4. Create Custom Search Engine: https://programmablesearchengine.google.com/
5. Copy Search Engine ID (cx parameter)

**Tavily API (Optional - 1000 queries/month free):**
1. Sign up at https://tavily.com/
2. Get API key from dashboard
3. Copy `tvly-...` key

**Note:** DuckDuckGo requires no API key and is always available as fallback.

---

### Step 6: Update Model in Docker Compose

Edit `docker-compose.yml` to match the model you pulled:

```bash
# Open docker-compose.yml
nano docker-compose.yml

# Find line 31:
# OLLAMA_MODEL=phi4-mini:3.8b

# Change to your model:
# OLLAMA_MODEL=llama3:8b
# OLLAMA_MODEL=llama3:70b
# OLLAMA_MODEL=llama3:405b

# Save and exit (Ctrl+O, Enter, Ctrl+X in nano)
```

Or use sed to change it automatically:

```bash
# Change to llama3:70b (Mac Mini M4 / AMD Ryzen AI Max)
sed -i 's/OLLAMA_MODEL=.*/OLLAMA_MODEL=llama3:70b/' docker-compose.yml

# Verify the change
grep OLLAMA_MODEL docker-compose.yml
```

---

### Step 7: Start Services

```bash
# Build and start all services
docker-compose up -d

# View logs (optional)
docker-compose logs -f

# Check running containers
docker-compose ps
```

Expected output:
```
NAME      IMAGE              STATUS         PORTS
gateway   securebot-gateway  Up 10 seconds  0.0.0.0:8080->8080/tcp
vault     securebot-vault    Up 10 seconds  0.0.0.0:8200->8200/tcp
```

---

### Step 8: Verify Installation

#### Health Checks

```bash
# Gateway health
curl http://localhost:8080/health

# Expected output:
# {"status":"healthy","version":"2.0.0","ollama_connected":true,...}

# Vault health
curl http://localhost:8200/health

# Expected output:
# {"status":"healthy","version":"1.0.0","secrets_loaded":2,"search_providers":["google","tavily","duckduckgo"],...}

# Ollama health
curl http://localhost:11434/api/tags

# Expected output:
# {"models":[{"name":"phi4-mini:3.8b",...}]}
```

---

### Step 9: Send First Message

```bash
# Simple query (uses Ollama - FREE)
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "test-user",
    "text": "What is Python?"
  }'
```

**Expected response time:**
- Budget hardware (phi4-mini): 30-50 seconds
- Mid-range (llama3:8b): 15-30 seconds
- Mac Mini M4 (llama3:70b): 3-5 seconds
- GPU server: <1 second

🎉 **Congratulations! SecureBot is running!**

---

## 🔧 Configuration

### Optional User Configuration

Create `~/.securebot/config.yml` for advanced settings:

```bash
# Create config directory
mkdir -p ~/.securebot

# Create config file
cat > ~/.securebot/config.yml << 'EOF'
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
EOF
```

See [CONFIGURATION.md](CONFIGURATION.md) for complete reference.

---

## ✅ Verification

### Test All Features

```bash
# 1. Simple query (Ollama)
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"channel":"api","user_id":"test","text":"Explain variables in Python"}'

# 2. Search query (multi-provider)
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"channel":"api","user_id":"test","text":"What are the latest AI trends?"}'

# 3. Check search usage
curl http://localhost:8200/search/usage
```

---

## 🔧 Troubleshooting

### Problem: "Connection refused" to Ollama

**Symptoms:**
```
Error connecting to Ollama at http://host.docker.internal:11434
```

**Solution:**
```bash
# 1. Check if Ollama is running
curl http://localhost:11434/api/tags

# 2. If not running, start it:
ollama serve

# 3. On Linux, you might need to expose Ollama:
export OLLAMA_HOST=0.0.0.0:11434
ollama serve

# 4. Restart gateway container
docker-compose restart gateway
```

---

### Problem: Ollama running but model not found

**Symptoms:**
```
model 'llama3:70b' not found
```

**Solution:**
```bash
# 1. Check what models you have
ollama list

# 2. Pull the missing model
ollama pull llama3:70b

# 3. Or update docker-compose.yml to use a model you have
nano docker-compose.yml
# Change OLLAMA_MODEL to match what `ollama list` shows

# 4. Restart services
docker-compose restart
```

---

### Problem: Slow responses on budget hardware

**Symptoms:**
- Responses taking 60+ seconds
- High CPU usage

**Solution:**
```bash
# 1. Use a smaller model
ollama pull phi4-mini:3.8b

# 2. Update docker-compose.yml
nano docker-compose.yml
# Change: OLLAMA_MODEL=phi4-mini:3.8b

# 3. Restart
docker-compose restart gateway

# 4. On AMD systems, enable HSA_OVERRIDE_GFX_VERSION
export HSA_OVERRIDE_GFX_VERSION=9.0.0
ollama serve
```

---

### Problem: Gateway container exits immediately

**Symptoms:**
```
gateway container keeps restarting
```

**Solution:**
```bash
# 1. Check logs
docker-compose logs gateway

# 2. Common issues:
# - Vault not ready: Wait 30s and try again
# - Import errors: Rebuild containers
docker-compose build --no-cache
docker-compose up -d

# 3. Check if skills directory exists
ls -la /home/tasker0/securebot/skills/

# 4. Update volume mount in docker-compose.yml if needed
# Change line 33 to your actual path
```

---

### Problem: Vault secrets not loading

**Symptoms:**
```
"secrets_loaded": 0
```

**Solution:**
```bash
# 1. Check secrets file exists
cat vault/secrets/secrets.json

# 2. Validate JSON syntax
python3 -m json.tool vault/secrets/secrets.json

# 3. Check file permissions
chmod 644 vault/secrets/secrets.json

# 4. Restart vault
docker-compose restart vault

# 5. Check logs
docker-compose logs vault
```

---

### Problem: "Anthropic API key not configured"

**Symptoms:**
```
detail: "Anthropic API key not configured in vault"
```

**Solution:**
```bash
# 1. Add API key to secrets.json
nano vault/secrets/secrets.json

# Add:
# {
#   "anthropic_api_key": "sk-ant-api03-YOUR-KEY-HERE",
#   ...
# }

# 2. Restart vault
docker-compose restart vault

# 3. Verify it's loaded
curl http://localhost:8200/health
# Should show "secrets_loaded": 2 or more
```

---

### Problem: All search providers failing

**Symptoms:**
```
All search providers failed
```

**Solution:**
```bash
# 1. Check if at least DuckDuckGo is working
pip install duckduckgo-search

# Test manually:
python3 << 'EOF'
from ddgs import DDGS
ddg = DDGS()
results = list(ddg.text("test query", max_results=3))
print(results)
EOF

# 2. Install missing dependencies in vault container
docker-compose exec vault pip install duckduckgo-search

# Or rebuild:
docker-compose build vault
docker-compose up -d vault

# 3. Check search usage limits
curl http://localhost:8200/search/usage
```

---

### Problem: Port already in use

**Symptoms:**
```
Bind for 0.0.0.0:8080 failed: port is already allocated
```

**Solution:**
```bash
# 1. Find what's using the port
sudo lsof -i :8080
sudo lsof -i :8200

# 2. Stop conflicting service or change SecureBot ports
nano docker-compose.yml

# Change:
# ports:
#   - "8090:8080"  # Use 8090 instead of 8080
#   - "8210:8200"  # Use 8210 instead of 8200

# 3. Restart
docker-compose up -d
```

---

## 🎮 GPU Acceleration

### NVIDIA GPUs (CUDA)

**Automatic in Ollama** - no configuration needed if drivers installed.

```bash
# Verify CUDA is working
nvidia-smi

# Ollama will automatically use GPU
ollama pull llama3:70b
ollama run llama3:70b "test"

# Check GPU usage
nvidia-smi -l 1  # Updates every second
```

---

### AMD GPUs (ROCm)

**For discrete AMD GPUs:**

```bash
# Install ROCm (Ubuntu)
wget https://repo.radeon.com/amdgpu-install/latest/ubuntu/focal/amdgpu-install_*_all.deb
sudo dpkg -i amdgpu-install_*_all.deb
sudo amdgpu-install --usecase=rocm

# Set environment variables
export HSA_OVERRIDE_GFX_VERSION=10.3.0  # Adjust for your GPU

# Restart Ollama
ollama serve

# Verify GPU is detected
rocm-smi
```

**For integrated AMD GPUs (budget systems):**

```bash
# Enable GPU acceleration
export HSA_OVERRIDE_GFX_VERSION=9.0.0

# Restart Ollama
ollama serve

# Expect 2-3x speedup on integrated graphics
```

---

### AMD Ryzen AI Max (NPU + iGPU)

**For Windows with DirectML:**

```powershell
# 1. Install AMD Ryzen AI Software
# Download from AMD website

# 2. Enable DirectML in Ollama
$env:OLLAMA_ACCELERATION="directml"

# 3. Start Ollama
ollama serve

# 4. Pull and test
ollama pull llama3:70b
ollama run llama3:70b "test"
```

**For Linux:**

```bash
# Install ROCm for integrated graphics
sudo apt install rocm-hip-runtime

# Enable iGPU
export HSA_OVERRIDE_GFX_VERSION=11.0.0  # For Ryzen AI Max

# Start Ollama
ollama serve
```

---

### Apple Silicon (Metal)

**Automatic** - Metal acceleration is built-in on macOS.

```bash
# Verify Metal is working by checking speed
time ollama run llama3:70b "Explain quantum computing"

# Expected on Mac Mini M4:
# - llama3:70b: 3-5 seconds
# - llama3:405b (64GB model): 8-12 seconds
```

---

## 🔄 Upgrading

### Update SecureBot

```bash
cd securebot

# Pull latest changes
git pull origin main

# Rebuild containers
docker-compose build --no-cache

# Restart services
docker-compose down
docker-compose up -d

# Verify
curl http://localhost:8080/health
```

---

### Update Ollama Models

```bash
# Re-pull model to get latest version
ollama pull phi4-mini:3.8b
ollama pull llama3:8b
ollama pull llama3:70b

# Remove old models to save space
ollama rm old-model-name

# List all models
ollama list
```

---

### Update Docker Images

```bash
cd securebot

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache --pull
docker-compose up -d
```

---

## 📞 Getting Help

If you're still stuck:

1. **Check logs:** `docker-compose logs -f`
2. **Search issues:** https://github.com/Rojman1984/securebot/issues
3. **Ask community:** https://github.com/Rojman1984/securebot/discussions
4. **Create issue:** https://github.com/Rojman1984/securebot/issues/new

---

## ✅ Installation Complete!

You should now have:

- ✅ Docker & Ollama installed
- ✅ Model downloaded and ready
- ✅ SecureBot services running
- ✅ API responding to requests
- ✅ Search providers configured
- ✅ Health checks passing

**Next Steps:**

- 📖 Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand how it works
- 🧩 Learn about [SKILLS.md](SKILLS.md) to create reusable capabilities
- ⚙️ Configure [CONFIGURATION.md](CONFIGURATION.md) for your preferences
- 🖥️ Optimize [HARDWARE.md](HARDWARE.md) for best performance

---

**Happy building! 🚀**
