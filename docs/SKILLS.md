# SecureBot Skills Development Guide

## Table of Contents

1. [Introduction](#introduction)
2. [What is a Skill?](#what-is-a-skill)
3. [Skill File Format](#skill-file-format)
4. [Skill Categories](#skill-categories)
5. [Execution Modes](#execution-modes)
6. [Creating Your First Skill](#creating-your-first-skill)
7. [Testing Skills Locally](#testing-skills-locally)
8. [Placeholder Variables](#placeholder-variables)
9. [Skill Matching System](#skill-matching-system)
10. [Best Practices](#best-practices)
11. [Examples: Good vs Bad Skills](#examples-good-vs-bad-skills)
12. [Contributing Skills](#contributing-skills)
13. [Troubleshooting](#troubleshooting)

---

## Introduction

Skills are the building blocks of SecureBot's functionality. They enable the system to handle specific tasks through a modular, extensible architecture. Each skill is self-contained, well-documented, and can be easily added, modified, or removed without affecting other parts of the system.

**Why Skills Matter:**
- **Modularity**: Add new capabilities without changing core code
- **Maintainability**: Each skill is independent and easy to update
- **Discoverability**: Skills automatically match user queries based on descriptions
- **Flexibility**: Multiple execution modes support different use cases
- **Prioritization**: Control which skills are tried first for specific tasks

---

## What is a Skill?

A skill is a self-contained unit of functionality that:

1. **Defines its purpose** through metadata (name, description, category)
2. **Matches user queries** automatically using natural language keywords
3. **Executes actions** via different execution modes (Ollama, Claude Code, Vault)
4. **Respects priorities** to determine execution order
5. **Manages dependencies** like API keys or rate limits

### Skill Anatomy

```
skills/
└── my-skill/
    └── SKILL.md          # Skill definition with YAML frontmatter
```

Each skill lives in its own directory and contains a `SKILL.md` file with:
- **Frontmatter**: YAML metadata (name, description, category, etc.)
- **Documentation**: Markdown content explaining usage and examples

---

## Skill File Format

### Basic Structure

```markdown
---
name: skill-name
description: Natural language description with keywords for matching
category: general
priority: 10
requires_api_key: false
execution: vault-tool
tool_name: my_tool
---

# Skill Title

Brief overview of what this skill does.

## Usage

How to use this skill.

## Configuration

Any configuration requirements (API keys, environment variables).

## Examples

Example usage and expected output.
```

### YAML Frontmatter Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Unique identifier (kebab-case recommended) |
| `description` | string | Yes | - | Natural language description for query matching |
| `category` | string | No | `general` | Skill category (search, code, stt, tts, general) |
| `priority` | integer | No | `999` | Priority within category (lower = higher priority) |
| `requires_api_key` | boolean | No | `false` | Whether skill needs API credentials |
| `execution` | string | No | `vault-tool` | Execution mode (ollama, claude-code, vault-tool) |
| `tool_name` | string | No | - | Tool name for vault-tool execution |
| `disable-model-invocation` | boolean | No | `false` | Whether to disable LLM for this skill |

### Example: Complete Skill File

```markdown
---
name: search-google
description: Search the web using Google Custom Search API for general queries, coding questions, nutrition information, and planning
category: search
priority: 1
requires_api_key: true
execution: vault-tool
tool_name: google_search
---

# Google Custom Search

Perform web searches using Google Custom Search API.

## Provider Details

- **Provider**: Google Custom Search API
- **Free Tier**: 100 queries/day (3,000/month)
- **Best For**: General queries, coding, nutrition, planning
- **Requires API Key**: Yes

## Usage

This skill is automatically invoked when:
1. A search is needed (detected by gateway)
2. Google is the highest priority available provider
3. Rate limits have not been exceeded

## Configuration

Requires the following secrets in `/vault/secrets.json`:
```json
{
  "search": {
    "google_api_key": "your-api-key",
    "google_cx": "your-search-engine-id"
  }
}
```

## Priority

Priority 1 (highest) - Tried first when available.
```

---

## Skill Categories

Categories help organize skills and filter them for specific use cases.

### Available Categories

| Category | Purpose | Examples |
|----------|---------|----------|
| `search` | Web search providers | Google, Tavily, DuckDuckGo |
| `code` | Code generation and analysis | Python generators, code review |
| `stt` | Speech-to-text services | Whisper, Google STT |
| `tts` | Text-to-speech services | ElevenLabs, Google TTS |
| `general` | General-purpose utilities | String manipulation, calculators |

### Category Usage

```yaml
# Search provider skill
category: search

# Code generation skill
category: code

# General utility skill
category: general
```

**Category Filtering:**
- Gateway service filters `category: search` for search detection
- Orchestrator can filter by category when matching queries
- Skills can be excluded by category to prevent false matches

---

## Execution Modes

SecureBot supports three execution modes for different skill requirements.

### 1. vault-tool (Recommended for API Keys)

Executes tools in the Vault service where API keys are securely stored.

```yaml
execution: vault-tool
tool_name: google_search
requires_api_key: true
```

**Use Cases:**
- Search providers requiring API keys
- Services with rate limits
- Any external API requiring authentication

**Flow Diagram:**
```
User Query → Gateway → Orchestrator → Vault Service
                                          ↓
                                    Execute Tool
                                          ↓
                                    Return Results
```

### 2. claude-code (AI-Powered Execution)

Uses Claude Code CLI to execute skill instructions via LLM.

```yaml
execution: claude-code
disable-model-invocation: false
```

**Use Cases:**
- Code generation tasks
- Complex multi-step operations
- Tasks requiring AI reasoning

**Flow Diagram:**
```
User Query → Gateway → Orchestrator → Claude Code CLI
                                          ↓
                                    AI Processing
                                          ↓
                                    Generated Code/Output
```

### 3. ollama (Local LLM Execution)

Executes using local Ollama models for privacy-focused tasks.

```yaml
execution: ollama
model: llama3.2:1b
```

**Use Cases:**
- Offline processing
- Privacy-sensitive tasks
- Cost optimization (no API calls)

---

## Creating Your First Skill

### Step 1: Plan Your Skill

Answer these questions:
1. What specific task does this skill perform?
2. What category does it belong to?
3. Does it need API keys or external services?
4. What keywords should trigger this skill?
5. What priority should it have?

### Step 2: Create Skill Directory

```bash
cd /home/tasker0/securebot/skills
mkdir my-first-skill
cd my-first-skill
```

### Step 3: Create SKILL.md

```bash
cat > SKILL.md << 'EOF'
---
name: my-first-skill
description: Convert temperatures between Celsius and Fahrenheit for weather, cooking, and scientific calculations
category: general
priority: 20
requires_api_key: false
execution: claude-code
---

# Temperature Converter

Convert temperatures between Celsius and Fahrenheit scales.

## Usage

Ask to convert temperatures using natural language:
- "Convert 25 Celsius to Fahrenheit"
- "What is 98.6F in Celsius?"
- "Temperature conversion for 0 degrees C"

## Steps

The skill will:
1. Parse the temperature value and source unit
2. Apply the conversion formula
3. Return the converted temperature with proper units

## Examples

Input: "Convert 25C to F"
Output: "25°C is 77°F"

Input: "98.6 Fahrenheit to Celsius"
Output: "98.6°F is 37°C"
EOF
```

### Step 4: Test Your Skill

```bash
# Restart services to load new skill
docker-compose restart gateway

# Check if skill loaded
curl http://localhost:8080/skills | jq '.[] | select(.name=="my-first-skill")'

# Test with a query
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "cli",
    "user_id": "test",
    "text": "Convert 25 Celsius to Fahrenheit"
  }'
```

### Step 5: Iterate and Improve

- Check logs: `docker-compose logs gateway | grep "my-first-skill"`
- Refine description keywords if matching fails
- Adjust priority if other skills interfere
- Add more examples to documentation

---

## Testing Skills Locally

### Manual Testing

#### 1. Check Skill Loading

```bash
# View all loaded skills
curl http://localhost:8080/skills

# Filter by category
curl http://localhost:8080/skills | jq '.[] | select(.category=="search")'

# Check specific skill
curl http://localhost:8080/skills | jq '.[] | select(.name=="my-skill")'
```

#### 2. Test Query Matching

```bash
# Test a query
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "cli",
    "user_id": "test_user",
    "text": "your test query here"
  }'
```

#### 3. Check Logs

```bash
# Watch gateway logs
docker-compose logs -f gateway

# Check for skill matching
docker-compose logs gateway | grep "Matched skill"

# Check for errors
docker-compose logs gateway | grep ERROR
```

### Automated Testing

Create a test script `test_skill.py`:

```python
#!/usr/bin/env python3
import httpx
import json

def test_skill(query: str, expected_skill: str = None):
    """Test if query matches expected skill"""
    response = httpx.post(
        "http://localhost:8080/message",
        json={
            "channel": "cli",
            "user_id": "test",
            "text": query
        }
    )

    print(f"Query: {query}")
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        matched_skill = data.get("matched_skill")
        print(f"Matched skill: {matched_skill}")

        if expected_skill and matched_skill != expected_skill:
            print(f"❌ Expected {expected_skill}, got {matched_skill}")
        else:
            print(f"✅ Test passed")
    else:
        print(f"❌ Request failed: {response.text}")

    print("-" * 60)

# Run tests
test_skill("Convert 25C to F", "my-first-skill")
test_skill("Search for Python tutorials", "search-google")
test_skill("Reverse a string in Python", "python-string-reversal")
```

### Integration Testing

```bash
# Test full flow with actual execution
docker-compose logs -f gateway vault ollama

# In another terminal
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "cli",
    "user_id": "integration_test",
    "text": "search for SecureBot documentation"
  }' | jq
```

---

## Placeholder Variables

Skills can use placeholder variables that are automatically replaced during execution.

### Available Placeholders

| Placeholder | Replaced With | Use Case |
|------------|---------------|----------|
| `$ARGUMENTS` | User query arguments | Pass user input to skill |
| `${CLAUDE_SESSION_ID}` | Timestamp (YYYYMMDD_HHMMSS) | Unique session tracking |

### Using $ARGUMENTS

The `$ARGUMENTS` placeholder is replaced with the user's query text.

**Example Skill:**

```markdown
---
name: code-explainer
description: Explain code snippets in simple terms for learning and understanding
category: code
priority: 15
---

# Code Explainer

Explain the following code:

$ARGUMENTS

Provide a clear explanation including:
1. What the code does
2. How it works step-by-step
3. Any important concepts or patterns used
```

**Usage:**
```
User: "Explain this code: def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"
→ $ARGUMENTS is replaced with the entire query
```

### Using ${CLAUDE_SESSION_ID}

The `${CLAUDE_SESSION_ID}` placeholder provides a unique timestamp for session tracking.

**Example Skill:**

```markdown
---
name: session-logger
description: Log analysis session with timestamps
category: general
---

# Analysis Session ${CLAUDE_SESSION_ID}

Perform analysis: $ARGUMENTS

Save results with session ID for future reference.
```

**Result:**
```
Session: 20260216_143052
Analysis: User's query here
```

### Placeholder Behavior

**If $ARGUMENTS is present:**
```python
# Direct replacement
skill_content = skill_content.replace('$ARGUMENTS', user_query)
```

**If $ARGUMENTS is not present:**
```python
# Arguments appended to end
skill_content = skill_content + "\n\n" + user_query
```

**Session ID replacement:**
```python
# Always replaced when present
session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
skill_content = skill_content.replace('${CLAUDE_SESSION_ID}', session_id)
```

---

## Skill Matching System

Understanding how SecureBot matches user queries to skills helps you write better skill descriptions.

### Matching Algorithm

```
┌─────────────────────┐
│ User Query          │
│ "search for Python" │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────┐
│ 1. Normalize Query              │
│    - Convert to lowercase       │
│    - Extract key terms          │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ 2. Filter Skills                │
│    - Apply category filter      │
│    - Exclude disabled skills    │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ 3. Score Each Skill             │
│    - Trigger word matches (+3)  │
│    - Skill name match (+5)      │
│    - Description overlap (+1)   │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ 4. Select Best Match            │
│    - Highest score wins         │
│    - Minimum threshold required │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────┐
│ Execute Skill       │
└─────────────────────┘
```

### Scoring System

**Trigger Word Match (+3 points per match):**
- Extracted from skill description
- Filtered to remove common words
- Must be longer than 3 characters

**Skill Name Match (+5 points):**
- Query contains skill name (with dashes converted to spaces)
- Example: "search-google" matches "search google"

**Description Overlap (+1 point per word):**
- Common words between query and description
- After removing stop words

### Trigger Word Extraction

**Stop Words (Filtered Out):**
```python
stop_words = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'this', 'that', 'with', 'from', 'will', 'when', 'where', 'what', 'how',
    'your', 'you', 'any', 'all', 'can', 'use', 'using', 'used', 'useful',
    'data', 'text', 'string', 'function', 'method', 'code', 'program',
    'processing', 'manipulation', 'practice', 'algorithm', 'implementation'
}
```

**Good Trigger Words:**
- Action verbs: "search", "convert", "analyze"
- Domain nouns: "temperature", "weather", "cooking"
- Specific terms: "celsius", "fahrenheit", "google"

### Category Filtering

**Include by Category:**
```python
# Only match search skills
matcher.find_matching_skill("search for Python", category="search")
```

**Exclude by Category:**
```python
# Match any skill except search
matcher.find_matching_skill("reverse string", exclude_categories=["search"])
```

### Writing Descriptions for Good Matching

**Keyword-Rich Description (Good):**
```yaml
description: Search the web using Google Custom Search API for general queries, coding questions, nutrition information, and planning
```

**Triggers:** search, google, custom, queries, coding, questions, nutrition, information, planning

**Generic Description (Bad):**
```yaml
description: A search provider
```

**Triggers:** provider (only)

**Best Practices:**
1. Include action verbs users might say
2. List specific use cases and domains
3. Use natural language, not just keywords
4. Add synonyms for common terms
5. Think about how users describe the task

---

## Best Practices

### 1. Single Responsibility Principle

Each skill should do ONE thing well.

**Good:**
```yaml
name: celsius-to-fahrenheit
description: Convert temperatures from Celsius to Fahrenheit
```

**Bad:**
```yaml
name: unit-converter
description: Convert temperatures, distances, weights, volumes, and currencies
```

**Why:** Specific skills match queries better and are easier to maintain.

### 2. Clear, Natural Descriptions

Write descriptions as if explaining to a user, not a machine.

**Good:**
```yaml
description: Search the web using DuckDuckGo for privacy-focused searches with no API key required
```

**Bad:**
```yaml
description: DuckDuckGo search provider implementation
```

### 3. Appropriate Priority Values

**Priority Guidelines:**

```
1-3    → Critical/Preferred providers (search services)
10-20  → Common general skills (frequently used)
30-50  → Specialized skills (specific use cases)
100+   → Rare/fallback skills
999    → Default (lowest priority)
```

**Example:**
```yaml
# High priority for preferred search provider
name: search-google
priority: 1

# Medium priority for common utility
name: temperature-converter
priority: 20

# Low priority for specialized tool
name: advanced-regex-builder
priority: 50
```

### 4. Comprehensive Documentation

Include all sections in your skill:

```markdown
---
# Frontmatter with all relevant fields
---

# Skill Title
Brief overview paragraph

## Usage
How and when to use this skill

## Configuration
Required API keys, environment variables, dependencies

## Examples
Concrete examples with input and expected output

## Notes
Any limitations, rate limits, or important considerations
```

### 5. Keep Content Concise

**Guidelines:**
- Skills should be under 500 lines
- Use clear, actionable instructions
- Focus on the essential information
- Link to external docs for details

### 6. Test Thoroughly

Before contributing:
1. Test skill loads correctly
2. Verify query matching works
3. Test execution produces expected results
4. Check edge cases and error handling
5. Review logs for warnings or errors

### 7. Consistent Naming

**Naming Convention:**
- Use kebab-case: `my-skill-name`
- Be descriptive: `search-google` not `google`
- Include provider/method: `search-tavily` not `tavily-skill`

**Good Names:**
```
search-google
search-duckduckgo
temperature-converter
python-string-reversal
code-explainer
```

**Bad Names:**
```
google (too generic)
search-1 (not descriptive)
mySkill (wrong case)
search_google (wrong separator)
```

### 8. API Key Management

**For skills requiring API keys:**

```yaml
requires_api_key: true
execution: vault-tool
tool_name: my_api_tool
```

**Documentation:**
```markdown
## Configuration

Requires the following secrets in `/vault/secrets.json`:
```json
{
  "my_service": {
    "api_key": "your-key-here",
    "api_secret": "your-secret-here"
  }
}
```

Also requires implementation in `/vault/vault_service.py`.
```

---

## Examples: Good vs Bad Skills

### Example 1: Search Provider

**Good Skill:**

```markdown
---
name: search-tavily
description: Search the web using Tavily AI for research, fact-checking, and comprehensive information gathering with AI-powered relevance
category: search
priority: 2
requires_api_key: true
execution: vault-tool
tool_name: tavily_search
---

# Tavily AI Search

AI-powered web search with high-quality, relevant results.

## Provider Details

- **Provider**: Tavily AI
- **Free Tier**: 1,000 searches/month
- **Best For**: Research, fact-checking, comprehensive information
- **Requires API Key**: Yes

## Usage

Automatically invoked when:
1. Search is needed
2. Tavily is highest priority available
3. Rate limits not exceeded

## Configuration

Requires `/vault/secrets.json`:
```json
{
  "search": {
    "tavily_api_key": "your-api-key"
  }
}
```
```

**Bad Skill:**

```markdown
---
name: tavily
description: Search provider
category: search
---

# Tavily

Searches stuff.
```

**Why Bad:**
- Description too generic (poor matching)
- Missing priority (defaults to 999)
- No API key information
- No usage documentation
- Incomplete frontmatter

### Example 2: Code Generation

**Good Skill:**

```markdown
---
name: python-string-reversal
description: Creates a Python function to reverse a string using various methods including slicing, loops, and built-in functions. Useful for string manipulation, algorithm practice, text processing, and when you need to reverse text data in Python programs.
category: code
priority: 25
execution: claude-code
---

# Python String Reversal Function

Creates a complete Python function to reverse any input string.

## Usage

This skill generates Python code to reverse strings. Common use cases:
- Text processing and transformation
- Palindrome checking
- Data manipulation
- Algorithm implementation practice

## Steps

1. Define function signature with string parameter
2. Choose reversal method (slicing, loop, or built-in)
3. Implement reversal logic
4. Add input validation
5. Include return statement
6. Add documentation and examples
7. Provide test cases

## Output Format

Returns complete Python code including:
- Function definition with docstring
- Implementation (specified or default method)
- Error handling for edge cases
- Example usage and test cases
- Performance notes

## Examples

Basic: "reverse a string in Python"
Specific: "reverse string using slicing method"
With validation: "reverse string function with error handling"
```

**Bad Skill:**

```markdown
---
name: string-reverse
description: Reverse strings
---

Reverse a string: $ARGUMENTS
```

**Why Bad:**
- Description too short (poor matching)
- No category or priority
- No documentation
- No examples or guidance
- Missing execution mode

### Example 3: Utility Tool

**Good Skill:**

```markdown
---
name: json-formatter
description: Format and validate JSON data with proper indentation, syntax checking, and error highlighting for debugging APIs, config files, and data structures
category: general
priority: 30
execution: claude-code
---

# JSON Formatter and Validator

Format, validate, and beautify JSON data with detailed error reporting.

## Usage

Use when you need to:
- Format minified or ugly JSON
- Validate JSON syntax
- Debug JSON parsing errors
- Pretty-print API responses
- Check JSON structure

## Features

1. **Syntax Validation**: Checks for valid JSON structure
2. **Pretty Printing**: Adds proper indentation
3. **Error Detection**: Highlights syntax errors with line numbers
4. **Minification**: Option to compact JSON
5. **Type Checking**: Validates data types

## Examples

**Input:**
```
{"name":"John","age":30,"city":"New York"}
```

**Output:**
```json
{
  "name": "John",
  "age": 30,
  "city": "New York"
}
```

## Edge Cases Handled

- Trailing commas
- Single vs double quotes
- Nested structures
- Unicode characters
- Empty objects/arrays
```

**Bad Skill:**

```markdown
---
name: json-tool
description: JSON stuff
---

# JSON Tool

Does JSON things with $ARGUMENTS
```

**Why Bad:**
- Vague description (no keywords)
- No use cases listed
- No examples
- Minimal documentation
- No feature explanation

---

## Contributing Skills

### Contribution Process

1. **Create Your Skill**
   - Follow the skill format
   - Write comprehensive documentation
   - Test thoroughly locally

2. **Prepare Submission**
   ```bash
   # Ensure skill file is well-formed
   cd /home/tasker0/securebot/skills/your-skill
   cat SKILL.md

   # Test skill loading
   docker-compose restart gateway
   curl http://localhost:8080/skills | jq '.[] | select(.name=="your-skill")'
   ```

3. **Commit Changes**
   ```bash
   git add skills/your-skill/
   git commit -m "Add your-skill: brief description"
   ```

4. **Submit Pull Request**
   - Create feature branch
   - Push to GitHub
   - Open pull request with description

### Contribution Checklist

- [ ] Skill follows naming conventions (kebab-case)
- [ ] YAML frontmatter is valid and complete
- [ ] Description is keyword-rich and natural
- [ ] Category and priority are appropriate
- [ ] Documentation includes all sections
- [ ] Examples demonstrate usage clearly
- [ ] Skill loads without errors
- [ ] Query matching works as expected
- [ ] Execution completes successfully
- [ ] No secrets or API keys in skill file
- [ ] Code follows project style guidelines

### Review Process

**Reviewers Check:**
1. Skill solves a real use case
2. No duplicates or significant overlap
3. Documentation is clear and complete
4. Implementation follows best practices
5. Security considerations addressed
6. Testing proves functionality

### After Approval

Once merged:
1. Skill available to all users
2. Listed in skill directory
3. Automatically loaded by gateway
4. Available for query matching

---

## Troubleshooting

### Skill Not Loading

**Symptoms:**
- Skill doesn't appear in `/skills` endpoint
- No "Loaded skill" message in logs

**Solutions:**

1. **Check YAML Syntax**
   ```bash
   # Validate YAML frontmatter
   python3 << EOF
   import yaml
   with open('skills/my-skill/SKILL.md') as f:
       content = f.read()
       if content.startswith('---\n'):
           parts = content.split('---\n', 2)
           try:
               metadata = yaml.safe_load(parts[1])
               print("✅ Valid YAML")
               print(metadata)
           except yaml.YAMLError as e:
               print(f"❌ YAML Error: {e}")
   EOF
   ```

2. **Check File Location**
   ```bash
   # Ensure SKILL.md exists in skill directory
   ls -la skills/my-skill/SKILL.md
   ```

3. **Check Disabled Skills**
   ```bash
   # View config
   cat ~/.securebot/config.yml | grep -A5 disabled_skills
   ```

4. **Check Logs**
   ```bash
   docker-compose logs gateway | grep -i "my-skill"
   ```

### Skill Not Matching Queries

**Symptoms:**
- Different skill matches instead
- No skill matches (generic response)

**Solutions:**

1. **Test Trigger Words**
   ```bash
   # Extract triggers from description
   python3 << 'EOF'
   description = "Your skill description here"
   words = description.lower().split()
   stop_words = {'the', 'a', 'an', 'and', 'or', 'in', 'on', 'at'}
   triggers = [w for w in words if w not in stop_words and len(w) > 3]
   print("Triggers:", triggers)
   EOF
   ```

2. **Improve Description**
   - Add more specific keywords
   - Include use case examples
   - Use natural language phrases

3. **Check Priority**
   - Lower priority = tried first
   - Verify no higher priority skill matches same query

4. **Test Explicitly**
   ```bash
   curl -X POST http://localhost:8080/message \
     -H "Content-Type: application/json" \
     -d '{"channel":"cli","user_id":"test","text":"my-skill exact name"}' \
     | jq '.matched_skill'
   ```

### Skill Execution Fails

**Symptoms:**
- Error during execution
- Timeout or unexpected response

**Solutions:**

1. **Check Execution Mode**
   ```yaml
   # For vault-tool, ensure tool exists in vault_service.py
   execution: vault-tool
   tool_name: my_tool  # Must be implemented
   ```

2. **Check API Keys**
   ```bash
   # For requires_api_key: true
   docker-compose exec vault cat /vault/secrets.json | jq
   ```

3. **Check Rate Limits**
   ```bash
   # View usage stats
   curl http://localhost:8083/usage
   ```

4. **Check Logs**
   ```bash
   # View vault logs for execution errors
   docker-compose logs vault | grep ERROR

   # View claude-code logs
   docker-compose logs ollama | tail -100
   ```

### Priority Not Working

**Symptoms:**
- Lower priority skill executes first
- Expected skill never runs

**Solutions:**

1. **Verify Priority Values**
   ```bash
   # Check all skills in category
   curl http://localhost:8080/skills | \
     jq '.[] | select(.category=="search") | {name, priority}'
   ```

2. **Check Config Overrides**
   ```bash
   # User config may override priorities
   cat ~/.securebot/config.yml | grep -A10 search_priority
   ```

3. **Understand Priority Logic**
   ```
   Priority 1 = Highest (tried first)
   Priority 999 = Lowest (last resort)

   Skills sorted: [1, 2, 3, ..., 999]
   ```

### Common Errors

**Error: "Invalid YAML frontmatter"**
```bash
# Check for proper --- delimiters
head -n 10 skills/my-skill/SKILL.md

# Should start with:
---
name: my-skill
...
---
```

**Error: "Tool not found"**
```bash
# For vault-tool execution, implement in vault_service.py
grep "def my_tool" vault/vault_service.py

# Or use different execution mode
execution: claude-code  # Instead of vault-tool
```

**Error: "Category filter mismatch"**
```bash
# Gateway filters by category
# Ensure category is correct
curl http://localhost:8080/skills | \
  jq '.[] | select(.name=="my-skill") | .category'
```

---

## Additional Resources

### Project Documentation

- **Architecture**: `/home/tasker0/securebot/docs/ARCHITECTURE.md`
- **Migration Guide**: `/home/tasker0/securebot/MIGRATION.md`
- **Quick Start**: `/home/tasker0/securebot/QUICKSTART.md`
- **Skills README**: `/home/tasker0/securebot/skills/README.md`

### Code References

- **Orchestrator**: `/home/tasker0/securebot/gateway/orchestrator.py`
- **Vault Service**: `/home/tasker0/securebot/vault/vault_service.py`
- **Gateway Service**: `/home/tasker0/securebot/gateway/gateway_service.py`
- **Config Module**: `/home/tasker0/securebot/common/config.py`

### Example Skills

- **Search Provider**: `/home/tasker0/securebot/skills/search-google/SKILL.md`
- **Fallback Search**: `/home/tasker0/securebot/skills/search-duckduckgo/SKILL.md`
- **Code Generation**: `/home/tasker0/securebot/skills/python-string-reversal/SKILL.md`

### API Endpoints

```bash
# View all skills
curl http://localhost:8080/skills

# Send message (triggers skill matching)
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"channel":"cli","user_id":"test","text":"your query"}'

# Check health
curl http://localhost:8080/health

# View usage statistics
curl http://localhost:8083/usage
```

---

## Quick Reference

### Skill Template

```markdown
---
name: skill-name
description: Detailed description with keywords for matching
category: general
priority: 50
requires_api_key: false
execution: claude-code
---

# Skill Title

Brief overview.

## Usage

When and how to use this skill.

## Configuration

Requirements and setup.

## Examples

Concrete examples with expected output.
```

### Priority Levels

```
1-3    High (search providers, critical services)
10-20  Medium (common utilities)
30-50  Normal (specialized tools)
100+   Low (rare use cases)
999    Default/Fallback
```

### Execution Modes

```yaml
execution: vault-tool    # API keys, secure execution
execution: claude-code   # AI-powered, complex tasks
execution: ollama        # Local LLM, privacy-focused
```

### Testing Commands

```bash
# Check skill loads
curl http://localhost:8080/skills | jq '.[] | select(.name=="my-skill")'

# Test query
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"channel":"cli","user_id":"test","text":"test query"}'

# View logs
docker-compose logs gateway | grep "Matched skill"
```

---

**Last Updated**: 2026-02-16
**Version**: 1.0.0
**License**: MIT
