# SecureBot Skills

This directory contains skills that SecureBot can use to handle specific tasks.

## Skill-Based Architecture

Skills are self-contained units of functionality with:
- **Metadata**: Name, description, category, priority
- **Documentation**: Usage instructions and examples
- **Configuration**: Whether they require API keys, how they execute

## Available Skills

### Search Skills (Category: search)

These skills provide web search functionality with automatic fallback:

| Skill | Provider | Free Tier | API Key | Priority |
|-------|----------|-----------|---------|----------|
| `search-google` | Google Custom Search | 100/day, 3000/month | ✅ Yes | 1 (highest) |
| `search-tavily` | Tavily AI | 1000/month | ✅ Yes | 2 |
| `search-duckduckgo` | DuckDuckGo | Rate limited | ❌ No | 3 (fallback) |

### Other Skills

| Skill | Category | Description |
|-------|----------|-------------|
| `python-string-reversal` | general | Example skill for string reversal |

## Creating New Skills

### Skill File Format

Each skill is a directory with a `SKILL.md` file:

```
skills/
└── my-skill/
    └── SKILL.md
```

### SKILL.md Template

```markdown
---
name: my-skill
description: Clear description with natural keywords for matching
category: general
priority: 1
requires_api_key: false
execution: vault-tool
tool_name: my_tool
---

# Skill Name

Brief overview of what this skill does.

## Usage

How to use this skill.

## Configuration

Any required configuration (API keys, etc.)

## Examples

Example usage if helpful.
```

### Metadata Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique skill identifier (kebab-case) |
| `description` | Yes | What the skill does (used for matching) |
| `category` | No | Skill category (e.g., 'search', 'general') |
| `priority` | No | Priority within category (lower = higher) |
| `requires_api_key` | No | Whether skill needs API credentials |
| `execution` | No | How skill executes ('vault-tool', 'ollama', etc.) |
| `tool_name` | No | Tool name for vault execution |

### Categories

Current categories:
- **search**: Web search providers
- **general**: General-purpose skills

You can create new categories as needed.

## Skill Configuration

Skills can be enabled/disabled in `~/.securebot/config.yml`:

```yaml
skills:
  # Disable specific skills
  disabled_skills:
    - search-tavily
    - my-skill

  # Override priorities
  search_priority:
    search-google: 1
    my-search-provider: 2
```

## How Skills Are Used

### 1. Gateway Service
- Loads search skills for search detection
- Filters by category (category='search')
- Respects enabled/disabled configuration

### 2. Orchestrator
- Loads all skills at startup
- Matches queries to skills
- Filters by category when needed
- Sorts by priority

### 3. Vault Service
- Executes skills that need API keys
- Respects rate limits
- Implements provider fallback

## Skill Matching

Skills are matched to queries based on:
1. **Trigger words**: Keywords from description
2. **Name matching**: Query mentions skill name
3. **Description overlap**: Common words with query
4. **Category filtering**: Only match within category if specified

Example:
```python
# Find any matching skill
matcher.find_matching_skill("reverse a string")

# Find search skills only
matcher.find_matching_skill("search for Python", category="search")
```

## Best Practices

### Writing Good Skills

1. **Clear descriptions**: Use natural language with keywords
2. **Single responsibility**: One skill, one task
3. **Good naming**: Use kebab-case, descriptive names
4. **Complete documentation**: Explain usage, config, examples
5. **Appropriate priority**: Lower for preferred providers

### Description Guidelines

Good description (keyword-rich):
```yaml
description: Search the web using Google Custom Search API for general queries, coding questions, nutrition information, and planning
```

Bad description (too generic):
```yaml
description: A search provider
```

### Priority Guidelines

- **1-3**: Critical or preferred providers (search providers)
- **10-20**: Common general skills
- **50+**: Specialized or rarely-used skills
- **999**: Lowest priority (default)

## Testing Skills

### Check Skill Loading

```bash
curl http://localhost:8080/skills
```

### Test Skill Matching

Create a test query that should match your skill:
```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "cli",
    "user_id": "test",
    "text": "your test query here"
  }'
```

Check logs to see which skill matched:
```bash
docker-compose logs gateway | grep "Matched skill"
```

## Adding Search Providers

To add a new search provider:

1. **Create skill**: `skills/search-{provider}/SKILL.md`
2. **Implement provider**: Add to `vault/vault_service.py`
3. **Register**: Add to SearchOrchestrator.__init__
4. **Configure**: Add API keys to `/vault/secrets.json`

See `MIGRATION.md` for detailed steps.

## Troubleshooting

### Skill Not Loading

Check:
1. SKILL.md file exists in skill directory
2. YAML frontmatter is valid (use YAML validator)
3. Skill is not in disabled_skills list
4. Logs show "Loaded skill: {name}"

### Skill Not Matching

Improve:
1. Add more keywords to description
2. Check trigger word extraction
3. Test with explicit skill name in query
4. Verify category is correct

### Priority Not Working

Verify:
1. Priority is a number (not string)
2. Lower numbers = higher priority
3. Config priority overrides SKILL.md priority
4. Check logs for "Provider order"

## Resources

- **Migration Guide**: `/home/tasker0/securebot/MIGRATION.md`
- **Config Example**: `/home/tasker0/securebot/config/config.example.yml`
- **Orchestrator Code**: `/home/tasker0/securebot/gateway/orchestrator.py`
