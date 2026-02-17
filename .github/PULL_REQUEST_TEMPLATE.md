# Pull Request

## Description

**What does this PR do?**

Clear summary of the changes in this PR.

**Related Issue:**
Closes #[issue number]

---

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change that fixes an issue)
- [ ] ✨ New feature (non-breaking change that adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to change)
- [ ] 🧩 New skill (adds a reusable AI capability)
- [ ] 📝 Documentation (updates to docs only)
- [ ] 🔧 Configuration (changes to config files, dependencies)
- [ ] ♻️ Refactoring (code improvements without changing behavior)
- [ ] ✅ Tests (adding or updating tests)
- [ ] 🎨 Style (formatting, code style changes)

---

## Changes Made

**Modified files:**
- `path/to/file1.py` - What changed and why
- `path/to/file2.py` - What changed and why
- `docs/EXAMPLE.md` - What changed and why

**Key changes:**

1. Change 1 explanation
2. Change 2 explanation
3. Change 3 explanation

---

## Testing

**How was this tested?**

- [ ] Manual testing
- [ ] Automated tests added
- [ ] Tested on multiple platforms
- [ ] Integration tests

**Test commands run:**
```bash
# Paste test commands and results
docker-compose up -d
curl http://localhost:8080/health
# ... other tests
```

**Test results:**
```
Paste relevant test output
```

**Tested on:**
- OS: [e.g., Ubuntu 22.04, macOS 14]
- Docker: [version]
- Ollama Model: [e.g., phi4-mini:3.8b]
- Hardware: [e.g., Ryzen 5 16GB RAM]

---

## Screenshots (if applicable)

**Before:**
[Screenshot or output before changes]

**After:**
[Screenshot or output after changes]

---

## Skill-Specific Information

**If this PR adds a new skill, complete this section:**

**Skill Name:** `skill-name`

**Category:** search | code | stt | tts | general

**Execution Mode:** vault-tool | claude-code | ollama

**Requires API Key:** Yes/No (specify provider)

**Priority:** [1-999]

**Trigger Keywords:** "keyword1", "keyword2", "keyword3"

**Example Usage:**
```bash
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "api",
    "user_id": "test",
    "text": "Example query that triggers this skill"
  }'
```

**Expected Output:**
```
Example output from the skill
```

**Tested with Queries:**
- ✅ "Query that should match" - Matched successfully
- ✅ "Another matching query" - Matched successfully
- ❌ "Query that should not match" - Correctly didn't match

---

## Breaking Changes

**Does this PR introduce breaking changes?**

- [ ] Yes (explain below)
- [ ] No

**If yes, what breaks and how to migrate:**

1. Breaking change 1
   - **What breaks:**
   - **How to fix:**

---

## Documentation

- [ ] README.md updated (if needed)
- [ ] docs/ updated (if needed)
- [ ] SKILLS.md updated (for new skills)
- [ ] CONFIGURATION.md updated (for new config options)
- [ ] Inline code comments added/updated
- [ ] API documentation updated (if API changed)

---

## Checklist

### Code Quality
- [ ] My code follows the project's code style
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings or errors
- [ ] I have checked for potential security issues

### Testing
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing unit tests pass locally
- [ ] I have tested the changes manually
- [ ] I have tested on multiple scenarios/inputs

### Documentation
- [ ] I have updated the documentation accordingly
- [ ] I have added docstrings to new functions/classes
- [ ] My commit messages are clear and descriptive

### Dependencies
- [ ] I have not added unnecessary dependencies
- [ ] If dependencies were added, I updated requirements.txt/Dockerfile
- [ ] I have verified the changes work with existing dependencies

### Git
- [ ] My branch is up to date with main
- [ ] I have resolved all merge conflicts
- [ ] My commits are logical and well-organized
- [ ] I have not included unrelated changes

---

## Performance Impact

**Does this PR affect performance?**

- [ ] Improves performance (explain how)
- [ ] No performance impact
- [ ] Slight performance decrease (explain trade-off)
- [ ] Not applicable

**If performance is affected:**
- Benchmark results:
- Trade-off justification:

---

## Security Considerations

**Does this PR have security implications?**

- [ ] No security implications
- [ ] Security review needed (explain why)
- [ ] Fixes a security issue (CVE/issue reference)

**Security checklist:**
- [ ] No hardcoded secrets or API keys
- [ ] User input is validated
- [ ] No SQL injection, XSS, or command injection vulnerabilities
- [ ] Secrets are properly isolated in vault
- [ ] No sensitive data in logs

---

## Additional Notes

Any other information that reviewers should know?

---

## Reviewer Notes

**Areas needing special attention:**
-
-

**Questions for reviewers:**
-
-

---

## Deployment Notes

**Special deployment steps:**
- [ ] No special steps needed
- [ ] Requires configuration changes (document below)
- [ ] Requires data migration (document below)
- [ ] Requires service restart

**If special steps needed:**
```bash
# Document deployment commands here
```

---

**Thank you for contributing to SecureBot! 🎉**

We appreciate your time and effort in improving this project.
