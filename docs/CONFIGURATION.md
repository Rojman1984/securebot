# SecureBot Configuration Reference

Complete configuration reference for SecureBot - a cost-optimized AI assistant with secure secrets management and intelligent routing.

## Table of Contents

1. [Configuration Files Overview](#configuration-files-overview)
2. [Secrets Configuration](#secrets-configuration)
3. [User Configuration](#user-configuration)
4. [Environment Variables](#environment-variables)
5. [Skill Configuration](#skill-configuration)
6. [Rate Limit Configuration](#rate-limit-configuration)
7. [Search Detection Modes](#search-detection-modes)
8. [Model Configuration](#model-configuration)
9. [Provider-Specific Settings](#provider-specific-settings)
10. [Configuration Examples](#configuration-examples)

---

## Configuration Files Overview

SecureBot uses a multi-layered configuration approach:

| File | Purpose | Location | Required |
|------|---------|----------|----------|
| `secrets.json` | API keys and sensitive credentials | `/vault/secrets.json` (in container) | Yes |
| `config.yml` | User preferences and overrides | `~/.securebot/config.yml` | No |
| `docker-compose.yml` | Infrastructure and environment variables | Project root | Yes |

**Configuration Priority**: User config (`~/.securebot/config.yml`) > Project config (`/home/tasker0/securebot/config/config.yml`) > Defaults (hardcoded)

---

## Secrets Configuration

### File Location

**Host**: `/home/tasker0/securebot/vault/secrets/secrets.json`
**Container**: `/vault/secrets.json` (mounted volume)

### Structure

```json
{
  "anthropic_api_key": "sk-ant-api03-...",
  "search": {
    "tavily_api_key": "tvly-...",
    "brave_api_key": "PLACEHOLDER",
    "google_api_key": "AIza...",
    "google_cx": "your-search-engine-id"
  },
  "telegram_bot_token": "PLACEHOLDER"
}
```

### Fields

#### `anthropic_api_key` (Required for Claude API features)
- **Type**: String
- **Purpose**: Anthropic API key for Claude API calls
- **Used For**:
  - Skill creation (complex tasks)
  - Direct Claude API calls (complex one-off queries)
- **Cost Impact**: High (charges per API call)
- **Get Key**: https://console.anthropic.com/

#### `search` Object
Container for search provider API keys.

##### `search.tavily_api_key`
- **Type**: String
- **Purpose**: Tavily API key for AI-optimized search
- **Free Tier**: 1,000 queries/month
- **Best For**: AI-optimized research, fact-finding, direct answers
- **Get Key**: https://tavily.com/
- **Optional**: Yes (can use Google or DuckDuckGo instead)

##### `search.google_api_key`
- **Type**: String
- **Purpose**: Google Custom Search API key
- **Free Tier**: 100 queries/day (3,000/month)
- **Best For**: General queries, coding, nutrition, planning
- **Get Key**: https://console.cloud.google.com/
- **Optional**: Yes (can use Tavily or DuckDuckGo instead)

##### `search.google_cx`
- **Type**: String
- **Purpose**: Google Custom Search Engine ID
- **Required If**: Using Google Custom Search
- **Get ID**: https://programmablesearchengine.google.com/

##### `search.brave_api_key`
- **Type**: String
- **Purpose**: Brave Search API key (not currently implemented)
- **Status**: Placeholder for future implementation

#### `telegram_bot_token`
- **Type**: String
- **Purpose**: Telegram Bot API token (not currently implemented)
- **Status**: Placeholder for future implementation

### Security Notes

- **Never commit** `secrets.json` to version control
- File is mounted as read-only volume in Docker
- Agent never sees API keys (injected at execution time by Vault)
- Use `VAULT_PASSWORD` environment variable for additional encryption (optional)

---

## User Configuration

### File Location

**Primary**: `~/.securebot/config.yml`
**Fallback**: `/home/tasker0/securebot/config/config.yml`

### Full Configuration Template

```yaml
# SecureBot User Configuration
# Copy this file to ~/.securebot/config.yml to customize

# Skill Configuration
skills:
  # Enable or disable specific skills
  # If not specified, all skills are enabled by default

  # Option 1: Explicitly list enabled skills (whitelist mode)
  # enabled_skills:
  #   - search-google
  #   - search-tavily
  #   - search-duckduckgo
  #   - python-string-reversal

  # Option 2: List disabled skills (blacklist mode - default)
  disabled_skills: []
  #   - search-tavily  # Example: disable Tavily to save monthly quota

  # Search provider priority override
  # Lower numbers = higher priority
  # If not specified, uses default priorities from SKILL.md files
  search_priority:
    search-google: 1      # Try Google first (if API key configured)
    search-tavily: 2      # Try Tavily second (if API key configured)
    search-duckduckgo: 3  # DuckDuckGo as fallback

# Gateway Configuration
gateway:
  # Search detection sensitivity
  # Options: strict, normal, relaxed
  # strict: Only trigger search on explicit phrases like "search for"
  # normal: Balanced detection (default)
  # relaxed: Trigger search more liberally
  search_detection: normal

  # Maximum search results to return
  max_search_results: 3

# Vault Configuration
vault:
  # Rate limit overrides (optional)
  # Use to be more conservative than provider defaults
  rate_limits:
    google:
      daily: 100      # Default: 100
      monthly: 3000   # Default: 3000
    tavily:
      monthly: 1000   # Default: 1000

# Orchestrator Configuration
orchestrator:
  # Skill creation threshold
  # Options: conservative, normal, aggressive
  # conservative: Create fewer skills, use direct Claude more often
  # normal: Balanced skill creation (default)
  # aggressive: Create skills more readily
  skill_creation: normal

  # Default model for Ollama
  ollama_model: "phi4-mini:3.8b"

  # Default Claude model for skill creation
  claude_model: "claude-sonnet-4-20250514"
```

---

## Environment Variables

Configured in `docker-compose.yml`:

### Vault Service

```yaml
environment:
  - VAULT_PASSWORD=${VAULT_PASSWORD:-change-me-in-production}
```

#### `VAULT_PASSWORD`
- **Default**: `change-me-in-production`
- **Purpose**: Additional encryption layer (optional, not currently used in code)
- **Recommendation**: Set in `.env` file or shell environment

### Gateway Service

```yaml
environment:
  - VAULT_URL=http://vault:8200
  - OLLAMA_HOST=http://host.docker.internal:11434
  - OLLAMA_MODEL=phi4-mini:3.8b
```

#### `VAULT_URL`
- **Default**: `http://vault:8200`
- **Purpose**: Internal URL to Vault service
- **Modify**: Only if changing service names in docker-compose

#### `OLLAMA_HOST`
- **Default**: `http://host.docker.internal:11434`
- **Purpose**: URL to Ollama server (host machine)
- **Note**: Uses `host.docker.internal` to access host from container
- **Modify**: If Ollama runs on different host/port

#### `OLLAMA_MODEL`
- **Default**: `phi4-mini:3.8b`
- **Purpose**: Default Ollama model for simple queries and skill execution
- **Options**: Any model installed in Ollama (`ollama list`)
- **Recommendations**:
  - `phi4-mini:3.8b` - Fast, low memory (3.8GB)
  - `phi4:14b` - Better quality, more memory (14GB)
  - `llama3.2:8b` - Balanced performance
  - `qwen2.5:14b` - High quality

---

## Skill Configuration

Skills are configured through the `skills` section in `config.yml`.

### Skill Enablement

#### Default Behavior (No Config)
All skills are enabled by default.

#### Blacklist Mode (Recommended)
Disable specific skills while keeping others enabled:

```yaml
skills:
  disabled_skills:
    - search-tavily  # Save Tavily quota
    - search-google  # Save Google quota, force DuckDuckGo
```

#### Whitelist Mode
Only enable specific skills:

```yaml
skills:
  enabled_skills:
    - search-duckduckgo  # Only free search
    - python-string-reversal
```

**Note**: If `enabled_skills` is specified, ONLY those skills are enabled. Otherwise, all skills except those in `disabled_skills` are enabled.

### Skill Priority

Control which search provider is tried first:

```yaml
skills:
  search_priority:
    search-google: 1      # Highest priority (tried first)
    search-tavily: 2      # Second priority
    search-duckduckgo: 3  # Lowest priority (fallback)
```

- **Lower number** = Higher priority
- Automatically falls back to next provider if:
  - Rate limit exceeded
  - API key not configured
  - Provider returns error

### Checking Skill Status

Skills are loaded from `/home/tasker0/securebot/skills/*/SKILL.md`.

View loaded skills:
```bash
curl http://localhost:8080/skills
```

---

## Rate Limit Configuration

Configure rate limits in `config.yml` under `vault.rate_limits`.

### Purpose
- Prevent exceeding provider free tiers
- Control costs
- Share quotas across multiple users

### Default Limits (Provider Free Tiers)

| Provider | Daily Limit | Monthly Limit |
|----------|-------------|---------------|
| Google | 100 | 3,000 |
| Tavily | N/A | 1,000 |
| DuckDuckGo | N/A (rate limited by IP) | N/A |

### Custom Limits

```yaml
vault:
  rate_limits:
    google:
      daily: 50      # Conservative: 50/day instead of 100
      monthly: 1500  # Conservative: 1500/month instead of 3000
    tavily:
      monthly: 500   # Conservative: 500/month instead of 1000
```

### Rate Limit Behavior

1. **Tracking**: Usage tracked in-memory by Vault service
2. **Checking**: Before each search, checks if provider is under limits
3. **Fallback**: If limit exceeded, tries next provider in priority order
4. **Reset**:
   - Daily: Resets at midnight (container timezone)
   - Monthly: Resets on 1st of month

### Monitoring Usage

```bash
curl http://localhost:8200/search/usage
```

Response:
```json
{
  "status": "success",
  "usage": {
    "google": {
      "daily": 15,
      "monthly": 245,
      "last_reset": "2026-02-16T10:30:00"
    },
    "tavily": {
      "daily": 0,
      "monthly": 8,
      "last_reset": "2026-02-01T00:00:00"
    }
  }
}
```

---

## Search Detection Modes

Controls when Gateway triggers web search. Configured in `config.yml` under `gateway.search_detection`.

### Modes

#### `strict` - Explicit Search Only
Only triggers on explicit search phrases:
- "search for"
- "find information about"
- "look up"

**Use When**:
- Minimizing search usage
- Most queries are conversational
- Want manual control

**Example**:
```yaml
gateway:
  search_detection: strict
```

#### `normal` - Balanced (Default)
Triggers on clear search intent:
- "search for"
- "find information about"
- "latest news about"
- "recent news about"
- "look up"

**Use When**:
- Balanced behavior (default)
- Mixed usage patterns
- Reasonable search frequency

#### `relaxed` - Liberal Search
Triggers on many information-seeking phrases:
- All "normal" triggers, plus:
- "search"
- "find"
- "what is"
- "who is"
- "latest"
- "recent"
- "news about"
- "information about"

**Use When**:
- Maximizing information freshness
- Research-heavy workload
- Have high rate limits

### Max Search Results

```yaml
gateway:
  max_search_results: 3  # Default: 3
```

- **Default**: 3 results
- **Range**: 1-10
- **Impact**:
  - More results = Better context
  - More results = Longer prompts
  - More results = Higher processing time

---

## Model Configuration

### Ollama Model (`orchestrator.ollama_model`)

```yaml
orchestrator:
  ollama_model: "phi4-mini:3.8b"
```

**Purpose**: Model used for:
- Simple direct queries
- Skill execution
- Search result summarization

**Changing Models**:
1. Pull model on host: `ollama pull <model>`
2. Update config: `ollama_model: "<model>"`
3. Restart containers: `docker-compose restart`

**Model Recommendations**:

| Model | RAM | Speed | Quality | Best For |
|-------|-----|-------|---------|----------|
| `phi4-mini:3.8b` | 4GB | Fast | Good | Default, skill execution |
| `phi4:14b` | 16GB | Medium | Better | Higher quality responses |
| `llama3.2:8b` | 8GB | Medium | Good | Balanced |
| `qwen2.5:14b` | 16GB | Medium | Great | Best quality |
| `llama3.1:8b` | 8GB | Fast | Good | Alternative to phi4 |

### Claude Model (`orchestrator.claude_model`)

```yaml
orchestrator:
  claude_model: "claude-sonnet-4-20250514"
```

**Purpose**: Model used for:
- Skill creation (complex tasks)
- Direct Claude calls (complex one-off queries)

**Cost Impact**: Every call costs money

**Available Models**:
- `claude-sonnet-4-20250514` - Balanced (default)
- `claude-opus-4-20250514` - Highest quality (expensive)
- `claude-3-5-sonnet-20241022` - Previous generation

---

## Provider-Specific Settings

### Google Custom Search

**Setup Requirements**:
1. Create Google Cloud project
2. Enable Custom Search API
3. Create API key
4. Create Custom Search Engine
5. Get Search Engine ID (CX)

**Configuration**:
```json
{
  "search": {
    "google_api_key": "AIzaSyD...",
    "google_cx": "a1b2c3d4e5f6g7h8i"
  }
}
```

**Rate Limits**:
- Free: 100/day, 3,000/month
- Paid: Contact Google for pricing

**Best For**:
- General queries
- Coding questions
- Nutrition information
- Planning tasks

### Tavily Search

**Setup Requirements**:
1. Sign up at https://tavily.com/
2. Get API key from dashboard

**Configuration**:
```json
{
  "search": {
    "tavily_api_key": "tvly-..."
  }
}
```

**Rate Limits**:
- Free: 1,000/month
- Paid: Various tiers

**Features**:
- AI-optimized results
- Direct answers
- Advanced search depth
- Fact-finding focused

**Best For**:
- Research tasks
- Fact-finding
- AI-optimized queries
- Direct answers

### DuckDuckGo Search

**Setup Requirements**: None (no API key needed)

**Configuration**: Automatically available (fallback)

**Rate Limits**:
- IP-based rate limiting
- No official published limits
- Generally generous for personal use

**Features**:
- No API key required
- Privacy-focused
- Free
- Unlimited (within reason)

**Best For**:
- Fallback provider
- Privacy-focused searches
- No API key scenarios
- Cost-free operation

---

## Configuration Examples

### Example 1: Minimal Free Setup (DuckDuckGo Only)

**Use Case**: No API keys, completely free operation

**secrets.json**:
```json
{
  "anthropic_api_key": "sk-ant-...",
  "search": {}
}
```

**config.yml**:
```yaml
skills:
  disabled_skills:
    - search-google
    - search-tavily
```

**Result**: Only DuckDuckGo for search, Ollama for all queries

### Example 2: Conservative Google + Tavily

**Use Case**: Preserve quotas, use both providers carefully

**secrets.json**:
```json
{
  "anthropic_api_key": "sk-ant-...",
  "search": {
    "google_api_key": "AIza...",
    "google_cx": "...",
    "tavily_api_key": "tvly-..."
  }
}
```

**config.yml**:
```yaml
skills:
  search_priority:
    search-tavily: 1     # Tavily first (better for research)
    search-google: 2     # Google second
    search-duckduckgo: 3 # DuckDuckGo fallback

gateway:
  search_detection: strict  # Only explicit searches
  max_search_results: 2     # Fewer results

vault:
  rate_limits:
    google:
      daily: 30
      monthly: 500
    tavily:
      monthly: 300
```

### Example 3: Research-Heavy Workload

**Use Case**: Maximize information freshness, high search usage

**secrets.json**:
```json
{
  "anthropic_api_key": "sk-ant-...",
  "search": {
    "google_api_key": "AIza...",
    "google_cx": "...",
    "tavily_api_key": "tvly-..."
  }
}
```

**config.yml**:
```yaml
skills:
  search_priority:
    search-google: 1     # Google first (larger quota)
    search-tavily: 2     # Tavily second
    search-duckduckgo: 3 # DuckDuckGo fallback

gateway:
  search_detection: relaxed  # Liberal search triggering
  max_search_results: 5      # More context

vault:
  rate_limits:
    google:
      daily: 100      # Use full quota
      monthly: 3000
    tavily:
      monthly: 1000   # Use full quota
```

### Example 4: Development/Testing

**Use Case**: Testing without consuming real quotas

**secrets.json**:
```json
{
  "anthropic_api_key": "sk-ant-...",
  "search": {}
}
```

**config.yml**:
```yaml
skills:
  disabled_skills:
    - search-google
    - search-tavily

gateway:
  search_detection: normal
  max_search_results: 3

vault:
  rate_limits:
    google:
      daily: 5   # Very conservative for testing
      monthly: 50
```

### Example 5: Cost-Optimized Production

**Use Case**: Minimize costs, maximize free tier usage

**secrets.json**:
```json
{
  "anthropic_api_key": "sk-ant-...",
  "search": {
    "google_api_key": "AIza...",
    "google_cx": "..."
  }
}
```

**config.yml**:
```yaml
skills:
  search_priority:
    search-duckduckgo: 1  # Free first
    search-google: 2      # Google second (100/day free)
  disabled_skills:
    - search-tavily       # Disable Tavily to save quota

gateway:
  search_detection: normal
  max_search_results: 3

orchestrator:
  skill_creation: conservative  # Create fewer skills (less Claude API usage)
  ollama_model: "phi4-mini:3.8b"  # Fastest, lowest resource

vault:
  rate_limits:
    google:
      daily: 80       # Leave headroom
      monthly: 2500
```

---

## Default Values Reference

### Built-in Defaults (No Config File)

From `common/config.py`:

```python
DEFAULT_CONFIG = {
    "skills": {
        "enabled_skills": None,  # None = all enabled
        "disabled_skills": [],
        "search_priority": {
            "search-google": 1,
            "search-tavily": 2,
            "search-duckduckgo": 3
        }
    },
    "gateway": {
        "search_detection": "normal",
        "max_search_results": 3
    },
    "vault": {
        "rate_limits": {
            "google": {
                "daily": 100,
                "monthly": 3000
            },
            "tavily": {
                "monthly": 1000
            }
        }
    },
    "orchestrator": {
        "skill_creation": "normal",
        "ollama_model": "phi4-mini:3.8b",
        "claude_model": "claude-sonnet-4-20250514"
    }
}
```

---

## Configuration Loading Order

1. **Defaults**: Hardcoded in `common/config.py`
2. **Project Config**: `/home/tasker0/securebot/config/config.yml` (if exists)
3. **User Config**: `~/.securebot/config.yml` (if exists)
4. **Environment Variables**: Override Ollama settings from `docker-compose.yml`

**Merge Strategy**: Deep merge (user config overrides defaults, keeps non-conflicting values)

---

## Troubleshooting

### Skills Not Loading

**Check**:
```bash
curl http://localhost:8080/skills
```

**Common Issues**:
- Skill disabled in config (`disabled_skills`)
- Skill file format invalid (YAML frontmatter parsing failed)
- Skills directory not mounted correctly

**Solution**:
```bash
# Check logs
docker-compose logs gateway | grep -i skill

# Verify skills directory
ls -la /home/tasker0/securebot/skills/*/SKILL.md
```

### Search Provider Not Working

**Check**:
```bash
curl http://localhost:8200/health
```

**Common Issues**:
- API key missing in `secrets.json`
- API key invalid or expired
- Rate limit exceeded
- Provider disabled in config

**Solution**:
```bash
# Check usage
curl http://localhost:8200/search/usage

# Check vault logs
docker-compose logs vault | grep -i search

# Verify secrets
docker exec securebot-vault-1 cat /vault/secrets.json
```

### Configuration Not Applied

**Check**:
```bash
# Gateway logs
docker-compose logs gateway | grep -i config

# Vault logs
docker-compose logs vault | grep -i config
```

**Common Issues**:
- Config file in wrong location
- YAML syntax error
- Services not restarted after config change

**Solution**:
```bash
# Validate YAML
python3 -c "import yaml; yaml.safe_load(open('~/.securebot/config.yml'))"

# Restart services
docker-compose restart
```

---

## Security Best Practices

1. **Never commit** `secrets.json` to version control
2. **Restrict file permissions**: `chmod 600 vault/secrets/secrets.json`
3. **Use environment variables** for `VAULT_PASSWORD` in production
4. **Rotate API keys** periodically
5. **Monitor usage** to detect anomalies: `curl http://localhost:8200/search/usage`
6. **Set conservative rate limits** to prevent quota exhaustion
7. **Use separate API keys** for dev/staging/production

---

## Performance Tuning

### For Speed
```yaml
orchestrator:
  ollama_model: "phi4-mini:3.8b"  # Fastest
gateway:
  max_search_results: 2  # Fewer results
```

### For Quality
```yaml
orchestrator:
  ollama_model: "qwen2.5:14b"  # Best quality
gateway:
  max_search_results: 5  # More context
```

### For Cost
```yaml
skills:
  search_priority:
    search-duckduckgo: 1  # Free first
orchestrator:
  skill_creation: conservative  # Less Claude API
```

---

## Support

For issues or questions:
- Check logs: `docker-compose logs`
- Review configuration: `curl http://localhost:8080/health`
- Validate secrets: `docker exec securebot-vault-1 cat /vault/secrets.json`
- Monitor usage: `curl http://localhost:8200/search/usage`
