# Migration Guide: Skill-Based Architecture

## Overview

SecureBot has been refactored from hard-coded search providers to a flexible skill-based architecture. This allows users to:

- Enable/disable search providers without code changes
- Configure provider priority
- Add new search providers as skills
- Control rate limits per provider
- Customize search detection sensitivity

## What Changed

### 1. **Search Providers are Now Skills**

Previously, search providers were hard-coded in:
- `gateway/gateway_service.py` (SearchDetector class)
- `vault/vault_service.py` (GoogleCustomSearch, TavilySearch, DuckDuckGoSearch classes)

Now:
- Each provider is a skill in `skills/search-{provider}/SKILL.md`
- Skills are loaded dynamically at runtime
- Skills can be enabled/disabled via configuration

### 2. **New Configuration System**

**Location**: `~/.securebot/config.yml` (optional)

**Example**: `config/config.example.yml` (copy this to get started)

**Configuration Options**:
```yaml
skills:
  # Disable specific search providers
  disabled_skills:
    - search-tavily  # Save monthly quota

  # Override provider priority (lower = higher priority)
  search_priority:
    search-google: 1
    search-tavily: 2
    search-duckduckgo: 3

gateway:
  # Search detection: strict, normal, relaxed
  search_detection: normal
  max_search_results: 3

vault:
  # Rate limit overrides
  rate_limits:
    google:
      daily: 50      # More conservative than default 100
      monthly: 1500  # More conservative than default 3000
```

### 3. **New Files and Directories**

```
securebot/
├── common/
│   ├── __init__.py
│   └── config.py              # New: Configuration management
├── config/
│   └── config.example.yml     # New: Example configuration
├── skills/
│   ├── search-google/
│   │   └── SKILL.md           # New: Google search skill
│   ├── search-tavily/
│   │   └── SKILL.md           # New: Tavily search skill
│   └── search-duckduckgo/
│       └── SKILL.md           # New: DuckDuckGo search skill
└── MIGRATION.md               # This file
```

### 4. **Modified Files**

**gateway/gateway_service.py**:
- `SearchDetector` class now loads search skills dynamically
- Supports configurable search detection sensitivity
- Imports from `common.config`

**gateway/orchestrator.py**:
- `SkillMatcher` now filters skills by user config
- Added `find_matching_skill(category="search")` for category filtering
- Added `get_skills_by_category()` method
- Skills expose `category` and `priority` metadata

**vault/vault_service.py**:
- `SearchOrchestrator` now respects user configuration
- Rate limits are configurable
- Provider priority is configurable
- Providers can be disabled entirely

## Backward Compatibility

### ✅ **100% Backward Compatible**

If you do **NOT** create a config file, everything works exactly as before:
- All search providers are enabled
- Default priorities are used (Google → Tavily → DuckDuckGo)
- Default rate limits are used
- Normal search detection sensitivity

### Configuration is Optional

You only need to create `~/.securebot/config.yml` if you want to customize behavior.

## Migration Steps

### For Regular Users

**No action required!** Everything continues to work as before.

### For Users Who Want Customization

1. **Copy example config**:
   ```bash
   mkdir -p ~/.securebot
   cp /home/tasker0/securebot/config/config.example.yml ~/.securebot/config.yml
   ```

2. **Edit configuration**:
   ```bash
   nano ~/.securebot/config.yml
   ```

3. **Customize as needed**:
   - Disable expensive providers to save quota
   - Adjust search detection sensitivity
   - Override rate limits
   - Change provider priority

4. **Restart services**:
   ```bash
   cd /home/tasker0/securebot
   docker-compose restart
   ```

### For Developers Adding New Search Providers

1. **Create skill directory**:
   ```bash
   mkdir -p skills/search-{provider}
   ```

2. **Create SKILL.md**:
   ```yaml
   ---
   name: search-{provider}
   description: Search using {provider}
   category: search
   priority: {number}
   requires_api_key: {true/false}
   execution: vault-tool
   tool_name: {provider}_search
   ---

   # Provider Name

   [Documentation here]
   ```

3. **Add provider implementation** to `vault/vault_service.py`:
   ```python
   class NewProviderSearch(SearchProvider):
       async def search(self, query: str, max_results: int):
           # Implementation
           pass
   ```

4. **Register in SearchOrchestrator** (in `__init__`):
   ```python
   if (config.get("provider_api_key") and
       self.user_config.is_skill_enabled("search-provider")):

       self.providers.append({
           "provider": NewProviderSearch(config["provider_api_key"]),
           "name": "provider",
           "priority": self.user_config.get_skill_priority("search-provider", 4)
       })
   ```

5. **No changes needed** to gateway or orchestrator!

## Configuration Reference

### Search Detection Modes

| Mode | Description | Examples |
|------|-------------|----------|
| `strict` | Only explicit search phrases | "search for", "look up", "find information about" |
| `normal` | Balanced detection (default) | Above + "latest news", "recent news" |
| `relaxed` | Liberal detection | Above + "what is", "who is", "find", "search" |

### Rate Limits

Configure conservative limits to preserve quotas:

```yaml
vault:
  rate_limits:
    google:
      daily: 50      # Default: 100
      monthly: 1500  # Default: 3000
    tavily:
      monthly: 500   # Default: 1000
```

### Skill Priority

Lower number = higher priority (tried first):

```yaml
skills:
  search_priority:
    search-google: 1      # Try first
    search-tavily: 2      # Try second
    search-duckduckgo: 3  # Fallback
```

### Disabling Skills

Save quotas by disabling providers:

```yaml
skills:
  disabled_skills:
    - search-tavily  # Disable Tavily to save 1000/month quota
```

## Testing

After migration, verify:

1. **Skills are loaded**:
   ```bash
   curl http://localhost:8080/skills
   ```

2. **Search works**:
   ```bash
   curl -X POST http://localhost:8080/message \
     -H "Content-Type: application/json" \
     -d '{
       "channel": "cli",
       "user_id": "test",
       "text": "search for Python tutorials"
     }'
   ```

3. **Configuration is respected**:
   - Check logs for "Provider order: [...]"
   - Verify disabled skills are skipped

## Troubleshooting

### Skills Not Loading

**Problem**: `/skills` endpoint returns empty list

**Solution**:
1. Check skills directory exists: `ls -la /home/tasker0/securebot/skills/`
2. Check SKILL.md files exist
3. Check YAML frontmatter is valid
4. Check logs for errors: `docker-compose logs gateway`

### Search Providers Not Available

**Problem**: Search fails with "All search providers failed"

**Solution**:
1. Check if providers are disabled in config
2. Verify API keys in `/vault/secrets.json`
3. Check rate limits haven't been exceeded
4. Verify provider order in logs

### Configuration Not Applied

**Problem**: Changes to config.yml not taking effect

**Solution**:
1. Verify config location: `~/.securebot/config.yml`
2. Check YAML syntax: `python3 -c "import yaml; yaml.safe_load(open('~/.securebot/config.yml'))"`
3. Restart services: `docker-compose restart`
4. Check logs for "Loaded user config from..."

## Benefits of New Architecture

1. **Extensibility**: Add new search providers without modifying core code
2. **Configurability**: Users control behavior without code changes
3. **Maintainability**: Search logic is isolated in skills
4. **Testability**: Skills can be tested independently
5. **Cost Control**: Disable expensive providers, set conservative rate limits
6. **Flexibility**: Change provider priority dynamically

## Future Enhancements

This architecture enables:

- User-defined custom search providers
- Per-user skill preferences
- A/B testing different provider combinations
- Dynamic skill loading from remote repositories
- Skill marketplace

## Questions?

Check logs for detailed information:
```bash
# Gateway logs (skill loading)
docker-compose logs gateway

# Vault logs (provider initialization)
docker-compose logs vault
```

For issues, check:
1. This migration guide
2. `config/config.example.yml` for examples
3. Service logs for errors
4. Skills documentation in `skills/*/SKILL.md`
