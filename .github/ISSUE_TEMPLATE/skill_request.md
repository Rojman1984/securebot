---
name: Skill Request
about: Request a new skill or suggest improvements to existing skills
title: '[SKILL] '
labels: skill, enhancement
assignees: ''
---

## Skill Overview

**Skill Name:**
[Suggested name in kebab-case, e.g., python-code-reviewer, log-file-analyzer]

**Category:**
- [ ] search - Web search providers
- [ ] code - Code analysis, generation, review
- [ ] stt - Speech-to-text
- [ ] tts - Text-to-speech
- [ ] general - Other capabilities

**One-line description:**
[Clear description of what this skill does]

---

## Use Case

**Problem this skill solves:**

Explain the problem or need this skill addresses.

**Who would benefit:**
- [ ] Developers
- [ ] Content creators
- [ ] Data analysts
- [ ] Researchers
- [ ] System administrators
- [ ] Other: ___________

**How often would this be used:**
- [ ] Daily
- [ ] Weekly
- [ ] Monthly
- [ ] Occasionally
- [ ] One-off but reusable pattern

---

## Skill Behavior

**Input:**

What does the skill take as input?
```
Example input format
```

**Expected Output:**

What should the skill return?
```
Example output format
```

**Example Usage:**
```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "test",
    "text": "Example query that would trigger this skill"
  }'
```

---

## Technical Details

**Execution Mode:**
- [ ] vault-tool (requires API integration)
- [ ] claude-code (Claude CLI execution)
- [ ] ollama (direct Ollama execution)

**API Requirements:**
- [ ] Requires API key (specify provider: _________)
- [ ] Uses existing SecureBot APIs (Claude, Search)
- [ ] No external API needed

**Dependencies:**
- [ ] Python packages: [list packages]
- [ ] External services: [list services]
- [ ] None

---

## Priority & Triggers

**Priority Level:**
- [ ] 1 (Highest - should be checked first)
- [ ] 2-3 (Medium)
- [ ] 4-999 (Lower priority)

**Trigger Keywords:**

What words or phrases should trigger this skill?

Example: "analyze", "security", "python", "vulnerability"

**Should trigger on:**
- "Query example 1 that should match"
- "Query example 2 that should match"

**Should NOT trigger on:**
- "Query example that should not match"
- "Query example that should not match"

---

## Skill Implementation

**Proposed Approach:**

If you have ideas on how to implement this, share them here!

**Skill Content Structure:**
```markdown
---
name: skill-name
description: Clear description with trigger keywords
category: code
priority: 2
requires_api_key: false
execution: ollama
---

# Skill Title

Instructions for what this skill does...

## Steps

1. First step
2. Second step
...
```

---

## Alternatives Considered

Have you tried other solutions? What are the trade-offs?

---

## Additional Context

- Links to relevant documentation
- Similar skills in other systems
- Examples from other projects
- Screenshots or mockups
- Any other context

---

## Are You Willing to Contribute?

- [ ] Yes, I can submit a PR with this skill
- [ ] Yes, I can help test the skill
- [ ] Yes, I can help with documentation
- [ ] No, but I can provide feedback during development
- [ ] Just requesting - someone else would need to implement

---

## Checklist

- [ ] I have searched existing skills to avoid duplicates
- [ ] I have provided clear use cases
- [ ] I have included example inputs/outputs
- [ ] I have specified the skill category
- [ ] I have considered trigger keywords
- [ ] I have checked if this requires external APIs
- [ ] I have read the [SKILLS.md](../../docs/SKILLS.md) guide
