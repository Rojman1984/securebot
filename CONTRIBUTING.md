# Contributing to SecureBot

> **Building the future of cost-optimized AI together**

Thank you for your interest in contributing to SecureBot! We welcome contributions from developers, AI enthusiasts, and anyone passionate about making powerful AI accessible and affordable.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Getting Started](#getting-started)
- [Contribution Workflow](#contribution-workflow)
- [Contributing Skills](#contributing-skills)
- [Contributing Code](#contributing-code)
- [Contributing Documentation](#contributing-documentation)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)
- [Pull Request Process](#pull-request-process)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Documentation Standards](#documentation-standards)
- [Community Guidelines](#community-guidelines)
- [Recognition](#recognition)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for everyone, regardless of:
- Experience level (beginners welcome!)
- Technical background
- Gender identity and expression
- Sexual orientation
- Disability
- Personal appearance
- Race or ethnicity
- Age
- Religion or belief system

### Our Standards

**Positive Behaviors:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Accepting constructive criticism gracefully
- Focusing on what's best for the community
- Showing empathy towards others
- Helping newcomers get started

**Unacceptable Behaviors:**
- Harassment, trolling, or insulting comments
- Personal or political attacks
- Publishing private information without consent
- Spam or self-promotion without value
- Any conduct inappropriate in a professional setting

### Enforcement

Violations can be reported to the project maintainers. All complaints will be reviewed and investigated promptly and fairly. Maintainers will respect privacy and security of reporters.

---

## How Can I Contribute?

There are many ways to contribute to SecureBot:

### 1. Create and Share Skills

**The most impactful contribution!** Skills are reusable AI capabilities that benefit all users.

- Code analysis skills
- Data processing skills
- Writing and content skills
- Development workflow skills
- Domain-specific expertise skills

See [Contributing Skills](#contributing-skills) section below.

---

### 2. Improve Core Code

- Fix bugs
- Optimize performance
- Add new features
- Improve error handling
- Enhance logging and monitoring

See [Contributing Code](#contributing-code) section below.

---

### 3. Enhance Documentation

- Fix typos and clarifications
- Add examples and tutorials
- Create video guides
- Translate to other languages
- Document edge cases and gotchas

See [Contributing Documentation](#contributing-documentation) section below.

---

### 4. Add Integrations

- New search providers (Brave, Perplexity, Kagi)
- Chat platforms (Telegram, Discord, Slack, WhatsApp)
- Voice interfaces (STT/TTS skills)
- IDE plugins
- Mobile apps

---

### 5. Improve Testing

- Write unit tests
- Add integration tests
- Create performance benchmarks
- Test on different hardware
- Document test results

---

### 6. Community Support

- Answer questions in Discussions
- Review pull requests
- Triage bug reports
- Mentor new contributors
- Share your SecureBot setup

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

1. **Development Environment:**
   - Python 3.10 or higher
   - Docker and Docker Compose
   - Git
   - Code editor (VS Code, PyCharm, Vim, etc.)

2. **SecureBot Running:**
   - Fork the repository
   - Clone your fork
   - Complete the installation steps
   - Verify services are working

3. **GitHub Account:**
   - Sign up at https://github.com
   - Configure SSH keys (recommended)
   - Set up two-factor authentication

### Fork and Clone

```bash
# Fork the repository on GitHub (click Fork button)

# Clone your fork
git clone https://github.com/YOUR_USERNAME/securebot.git
cd securebot

# Add upstream remote
git remote add upstream https://github.com/Rojman1984/securebot.git

# Verify remotes
git remote -v
```

### Create a Branch

```bash
# Update your main branch
git checkout main
git pull upstream main

# Create a feature branch
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
# or
git checkout -b docs/documentation-update
```

**Branch Naming Conventions:**
- `feature/` - New features
- `fix/` - Bug fixes
- `docs/` - Documentation changes
- `test/` - Testing improvements
- `refactor/` - Code refactoring
- `skill/` - New skills

---

## Contribution Workflow

### Standard Workflow

1. **Find or Create an Issue**
   - Check existing issues to avoid duplicates
   - Comment on the issue to claim it
   - Create new issue if needed

2. **Create a Branch**
   - Branch from `main`
   - Use descriptive branch names

3. **Make Changes**
   - Write clean, documented code
   - Follow style guidelines
   - Add tests if applicable

4. **Test Locally**
   - Run all tests
   - Test manually
   - Verify documentation builds

5. **Commit Changes**
   - Write clear commit messages
   - Reference issue numbers
   - Keep commits atomic

6. **Push to Your Fork**
   - Push your branch
   - Keep branch updated with main

7. **Create Pull Request**
   - Fill out PR template
   - Link related issues
   - Request review

8. **Address Feedback**
   - Respond to review comments
   - Make requested changes
   - Push updates

9. **Merge**
   - Maintainer merges PR
   - Delete your branch

---

## Contributing Skills

Skills are the heart of SecureBot's value proposition. A good skill can be reused thousands of times across the community.

### What Makes a Good Skill?

**Good Skill Candidates:**
- Repeated workflows (code review, testing, documentation)
- Domain expertise (security audit, performance optimization)
- Data processing patterns (parsing, transformation, validation)
- Content creation (writing, summarizing, formatting)
- Analysis tasks (complexity measurement, pattern detection)

**Poor Skill Candidates:**
- One-off questions ("What is Python?")
- Highly user-specific logic
- Tasks requiring external state
- Time-sensitive operations

### Skill Structure

Skills use Claude Code's SKILL.md format:

```markdown
---
name: descriptive-skill-name
description: Clear description with natural keywords for matching. Explain what the skill does and when to use it.
category: general|code|search|stt|tts|data|writing
priority: 1-999
disable-model-invocation: false
---

# Skill Title

Brief overview of what this skill does.

## Purpose

Explain the use case and value proposition.

## Usage

Describe how to use this skill and what inputs it expects.

## Steps

1. First step with clear instructions
2. Second step with details
3. Continue with all necessary steps
4. Include decision points if applicable

## Output Format

Describe the expected output structure and format.

## Examples

### Example 1: Basic Usage

Input: Sample input
Output: Expected output

### Example 2: Advanced Usage

Input: Complex input
Output: Expected output

## Notes

- Important considerations
- Edge cases to handle
- Limitations or constraints
```

### Skill Creation Checklist

- [ ] Skill addresses a reusable pattern
- [ ] YAML frontmatter is valid
- [ ] Description includes trigger keywords
- [ ] Category is appropriate
- [ ] Priority is set correctly
- [ ] Steps are clear and actionable
- [ ] Examples demonstrate usage
- [ ] Output format is specified
- [ ] SKILL.md is under 500 lines
- [ ] Tested with Ollama locally
- [ ] No hardcoded credentials or paths
- [ ] No external dependencies (unless documented)

### Submitting a Skill

1. **Create Skill Directory:**
   ```bash
   mkdir -p skills/your-skill-name
   cd skills/your-skill-name
   ```

2. **Write SKILL.md:**
   - Follow the format above
   - Be descriptive and clear
   - Include examples

3. **Test Locally:**
   ```bash
   # Restart gateway to load new skill
   docker-compose restart gateway

   # Test skill matching
   curl -X POST http://localhost:8080/message \
     -H "Content-Type: application/json" \
     -d '{
       "channel": "api",
       "user_id": "test",
       "text": "your test query that should match the skill"
     }'
   ```

4. **Document Usage:**
   - Add README.md in skill directory (optional)
   - Include any special setup or requirements

5. **Create Pull Request:**
   - Title: `skill: Add [skill-name] skill`
   - Description: Explain what the skill does and why it's useful
   - Include example usage in PR description

### Skill Review Criteria

Reviewers will check:
- **Quality:** Clear instructions, good examples
- **Usefulness:** Addresses a real need
- **Format:** Valid YAML, proper structure
- **Testing:** Works with Ollama
- **Documentation:** Sufficient explanation
- **Originality:** Not duplicate of existing skill

---

## Contributing Code

### Code Contribution Types

1. **Bug Fixes**
   - Fix reported issues
   - Add regression tests
   - Update documentation if needed

2. **Feature Implementation**
   - Implement approved features
   - Add comprehensive tests
   - Document new functionality

3. **Performance Optimization**
   - Profile and identify bottlenecks
   - Implement optimizations
   - Benchmark improvements

4. **Refactoring**
   - Improve code structure
   - Maintain backward compatibility
   - Document architectural changes

### Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # If exists

# Set up pre-commit hooks
pip install pre-commit
pre-commit install

# Run tests
pytest

# Run linter
flake8 .

# Type checking
mypy .
```

### Code Areas

**Core Components:**
- `gateway/gateway_service.py` - API gateway and routing
- `gateway/orchestrator.py` - Skill matching and complexity classification
- `vault/vault_service.py` - Secrets management
- `common/config.py` - Configuration management

**Adding New Components:**
- Follow existing patterns
- Keep services isolated
- Use Docker best practices
- Document architecture decisions

---

## Contributing Documentation

Good documentation is as important as good code!

### Documentation Types

1. **README Updates**
   - Main project overview
   - Quick start instructions
   - Feature highlights

2. **Technical Guides** (docs/)
   - Architecture documentation
   - API reference
   - Configuration guide
   - Hardware recommendations

3. **Tutorials**
   - Step-by-step guides
   - Common use cases
   - Troubleshooting

4. **Code Comments**
   - Docstrings for functions/classes
   - Inline comments for complex logic
   - Type hints

### Documentation Standards

**Style:**
- Clear, concise language
- Active voice preferred
- Present tense
- Second person ("you") for instructions

**Structure:**
- Start with overview/purpose
- Provide examples
- Include prerequisites
- End with troubleshooting

**Formatting:**
- Use Markdown
- Include code blocks with language syntax
- Add tables for comparisons
- Use headings for hierarchy

**Examples:**
- Show realistic use cases
- Include expected output
- Explain what the example demonstrates

---

## Reporting Bugs

Good bug reports help us fix issues faster.

### Before Reporting

1. **Search Existing Issues:** Check if already reported
2. **Test Latest Version:** Update to main branch
3. **Isolate the Problem:** Minimal reproduction steps
4. **Gather Information:** Logs, system info, configurations

### Bug Report Template

**Title:** Brief, descriptive summary

**Description:**
```
**Summary:**
What happened and what you expected

**Steps to Reproduce:**
1. First step
2. Second step
3. See error

**Expected Behavior:**
What should have happened

**Actual Behavior:**
What actually happened

**Environment:**
- OS: Linux/Mac/Windows
- Docker version: X.X.X
- Ollama version: X.X.X
- Model: phi4-mini / llama3:8b / etc
- Hardware: CPU/RAM/GPU

**Logs:**
```
Paste relevant logs here
```

**Additional Context:**
Any other relevant information
```

### Security Vulnerabilities

**Do NOT report security issues publicly.**

Email security concerns to: [maintainer email]

Include:
- Vulnerability description
- Reproduction steps
- Impact assessment
- Suggested fix (if any)

---

## Suggesting Features

We love feature ideas! Here's how to propose them:

### Feature Request Template

**Title:** [Feature] Brief description

**Description:**
```
**Problem:**
What problem does this solve?

**Proposed Solution:**
How should this work?

**Alternatives Considered:**
Other approaches you've thought about

**Use Case:**
Real-world scenario where this helps

**Implementation Notes:**
Any technical considerations (optional)

**Additional Context:**
Screenshots, examples, related issues
```

### Feature Discussion

1. **Create Discussion Thread** (preferred for ideas)
2. **Create Issue** (for concrete, actionable features)
3. **Comment on Existing Issues** (if related)

**Good Feature Requests:**
- Solve real problems
- Benefit multiple users
- Align with project goals
- Are technically feasible
- Include use cases

---

## Pull Request Process

### PR Checklist

Before submitting, ensure:

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New tests added for new code
- [ ] Documentation updated
- [ ] Commits are clean and descriptive
- [ ] Branch is up to date with main
- [ ] PR description is complete
- [ ] Related issues are linked

### PR Template

**Title:** Brief, descriptive summary

**Description:**
```
**Changes:**
- List key changes
- One per line

**Related Issues:**
Fixes #123
Relates to #456

**Type of Change:**
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update
- [ ] Skill addition

**Testing:**
Describe testing performed

**Screenshots:**
If applicable

**Checklist:**
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated Checks:** CI/CD runs tests
2. **Code Review:** Maintainer reviews code
3. **Feedback:** Reviewer comments on changes
4. **Revisions:** You address feedback
5. **Approval:** Maintainer approves PR
6. **Merge:** Code is merged to main

**Response Time:**
- Initial review: 1-3 days
- Follow-up reviews: 1-2 days
- Urgent fixes: Same day

### After Merge

- Delete your branch (GitHub offers button)
- Update your fork: `git pull upstream main`
- Close related issues if they're resolved
- Celebrate your contribution!

---

## Code Style Guidelines

### Python Style

**Follow PEP 8** with these specifics:

```python
# Imports: Standard library, third-party, local
import os
import sys
from typing import Dict, List, Optional

import httpx
from fastapi import FastAPI

from common.config import get_config

# Function naming: snake_case
def process_message(text: str) -> Dict[str, str]:
    """
    Process message and return response.

    Args:
        text: Input message text

    Returns:
        Response dictionary with result
    """
    pass

# Class naming: PascalCase
class MessageHandler:
    """Handle incoming messages with routing."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def handle(self, message: str) -> str:
        """Handle single message."""
        pass

# Constants: UPPERCASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30

# Private methods: _leading_underscore
def _internal_helper(data: str) -> str:
    """Internal helper function."""
    pass
```

**Key Points:**
- Use type hints for function signatures
- Write docstrings for public functions/classes
- Keep lines under 100 characters
- Use meaningful variable names
- Prefer explicit over implicit

### Markdown Style

```markdown
# Main Heading (H1)

Brief introduction paragraph.

## Section Heading (H2)

Content with proper spacing.

### Subsection (H3)

- Use bullet points for lists
- Keep items concise
- Parallel structure

**Bold** for emphasis, *italic* for terms.

```code blocks```
with proper syntax highlighting
```

**Tables:**
| Column 1 | Column 2 |
|----------|----------|
| Value    | Value    |
```

### YAML Style

```yaml
# Skills configuration
skills:
  enabled:
    - skill-name-one
    - skill-name-two

  priorities:
    skill-name-one: 1
    skill-name-two: 2

  rate_limits:
    provider:
      daily: 100
      monthly: 3000
```

---

## Testing Requirements

### Test Types

1. **Unit Tests**
   - Test individual functions
   - Mock external dependencies
   - Fast execution

2. **Integration Tests**
   - Test component interaction
   - Use test database/services
   - Moderate execution time

3. **End-to-End Tests**
   - Test full workflows
   - Real services
   - Slower execution

### Writing Tests

```python
import pytest
from gateway.orchestrator import ComplexityClassifier

class TestComplexityClassifier:
    """Test complexity classification logic."""

    def test_simple_query_classification(self):
        """Simple queries should use direct Ollama."""
        query = "What is Python?"
        result = ComplexityClassifier.classify(query, False)
        assert result == "direct_ollama"

    def test_complex_query_classification(self):
        """Complex queries should use Claude API."""
        query = "Design a scalable microservices architecture..."
        result = ComplexityClassifier.classify(query, False)
        assert result == "direct_claude"

    @pytest.mark.asyncio
    async def test_skill_execution(self):
        """Skills should execute successfully."""
        # Test skill execution logic
        pass
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_orchestrator.py

# Run with coverage
pytest --cov=gateway --cov=vault

# Run specific test
pytest tests/test_orchestrator.py::TestComplexityClassifier::test_simple_query_classification
```

### Test Requirements for PRs

- New features must include tests
- Bug fixes should include regression tests
- Maintain or improve code coverage
- All tests must pass before merge

---

## Documentation Standards

### Code Documentation

**Function Docstrings:**
```python
def calculate_cost(query_type: str, token_count: int) -> float:
    """
    Calculate cost for a query based on type and token count.

    Args:
        query_type: Type of query (simple, complex, skill_creation)
        token_count: Number of tokens in query

    Returns:
        Cost in USD

    Raises:
        ValueError: If query_type is invalid

    Example:
        >>> calculate_cost("simple", 500)
        0.003
    """
    pass
```

**Class Docstrings:**
```python
class GatewayService:
    """
    Gateway service with multi-channel message routing.

    Handles incoming messages from various channels (Telegram, API, CLI)
    and routes them through the orchestrator for processing.

    Attributes:
        vault_url: URL of the vault service
        ollama_url: URL of the Ollama service
        search_detector: SearchDetector instance
    """
    pass
```

### Inline Comments

```python
# Good: Explains why
# Use exponential backoff to avoid overwhelming the API during outages
retry_delay = 2 ** attempt

# Bad: Explains what (code is self-explanatory)
# Multiply 2 by attempt
retry_delay = 2 ** attempt
```

### README Updates

When adding features, update:
- Feature list
- Usage examples
- Configuration options
- API endpoints

---

## Community Guidelines

### Communication Channels

1. **GitHub Issues:** Bug reports, feature requests
2. **GitHub Discussions:** Questions, ideas, showcase
3. **Pull Requests:** Code review and collaboration

### Being a Good Community Member

**Do:**
- Be patient and respectful
- Help newcomers
- Provide constructive feedback
- Give credit where due
- Celebrate others' contributions
- Ask questions if unclear
- Admit when you don't know

**Don't:**
- Demand immediate responses
- Hijack threads
- Make assumptions about others
- Take criticism personally
- Gate-keep or be elitist
- Spam or self-promote excessively

### Reviewing Pull Requests

**Good Reviews:**
- Start with positive feedback
- Be specific about issues
- Suggest solutions, not just problems
- Explain the "why" behind requests
- Test the changes if possible
- Approve generously

**Review Template:**
```markdown
**Summary:**
Brief overview of the changes

**Strengths:**
- What's done well
- Good patterns used

**Suggestions:**
- Specific improvements
- With examples

**Questions:**
- Clarifications needed
- Alternative approaches

**Decision:**
- Approve / Request Changes / Comment
```

---

## Recognition

We value all contributions and recognize contributors in multiple ways:

### Contributor Recognition

1. **README Credits:** All contributors listed
2. **Release Notes:** Major contributions highlighted
3. **Community Showcase:** Feature interesting uses
4. **Skill Attribution:** Skill authors credited in SKILL.md

### Top Contributor Benefits

- Maintainer access (for sustained contributions)
- Input on project direction
- Priority support for your use cases
- Featured in community spotlights

### How to Get Recognized

Your contributions are automatically tracked via GitHub. We periodically update:
- Contributors list in README
- Skills directory with author attribution
- Release notes with change highlights

---

## Getting Help

### Stuck? Here's How to Get Help

1. **Read the Docs:** Check existing documentation first
2. **Search Issues:** Someone may have solved it
3. **GitHub Discussions:** Ask the community
4. **Create an Issue:** If it's a bug or missing feature

### Quick Links

- [Documentation](docs/)
- [FAQ](docs/FAQ.md) (if exists)
- [Architecture](docs/ARCHITECTURE.md)
- [Installation Guide](docs/INSTALL.md)

---

## Thank You!

Thank you for contributing to SecureBot! Every contribution, no matter how small, makes the project better for everyone.

**Your contributions help:**
- Make AI more accessible
- Reduce costs for everyone
- Build a stronger community
- Advance open-source AI tools

**Questions?** Feel free to:
- Open a Discussion thread
- Comment on related issues
- Reach out to maintainers

---

**Happy Contributing!**

Built with love by the SecureBot community.
