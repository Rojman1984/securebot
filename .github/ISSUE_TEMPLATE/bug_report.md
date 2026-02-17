---
name: Bug Report
about: Report a bug or unexpected behavior
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

**Clear and concise description of the bug**

What happened? What did you expect to happen?

---

## Environment

**System Information:**
- OS: [e.g., Ubuntu 22.04, macOS 14, Windows 11 WSL2]
- Docker Version: [run `docker --version`]
- Docker Compose Version: [run `docker compose version`]
- Ollama Version: [run `ollama --version`]
- Python Version: [if relevant, run `python3 --version`]

**SecureBot Configuration:**
- SecureBot Version/Commit: [e.g., main branch, commit abc123]
- Ollama Model: [e.g., phi4-mini:3.8b, llama3:8b, llama3:70b]
- Hardware: [e.g., Ryzen 5 3500U 16GB RAM, Mac Mini M4 32GB, etc.]

**Services Status:**
```bash
# Run these commands and paste output:
docker-compose ps
curl http://localhost:8080/health
curl http://localhost:8200/health
curl http://localhost:11434/api/tags
```

---

## Steps to Reproduce

1.
2.
3.
4.

**Minimal example to reproduce:**
```bash
# Paste curl command or code that reproduces the issue
curl -X POST http://localhost:8080/message \
  -H "Content-Type: application/json" \
  -d '{"channel":"api","user_id":"test","text":"your query here"}'
```

---

## Expected Behavior

What should have happened?

---

## Actual Behavior

What actually happened?

**Error messages:**
```
Paste any error messages, stack traces, or logs here
```

---

## Logs

**Gateway logs:**
```bash
docker-compose logs gateway
# Paste relevant logs here
```

**Vault logs:**
```bash
docker-compose logs vault
# Paste relevant logs here
```

**Ollama logs:**
```bash
# If Ollama is having issues, paste its logs
```

---

## Additional Context

- Does this happen consistently or intermittently?
- Did this work before? If so, what changed?
- Any custom configuration or modifications?
- Screenshots (if applicable):

---

## Possible Solution

If you have ideas on what might be causing this or how to fix it, please share!

---

## Checklist

- [ ] I have searched existing issues to avoid duplicates
- [ ] I have included all required environment information
- [ ] I have provided steps to reproduce the issue
- [ ] I have included relevant logs
- [ ] I have tested with the latest version
- [ ] I have checked the [INSTALL.md](../../docs/INSTALL.md) troubleshooting section
