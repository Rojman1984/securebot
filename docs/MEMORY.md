# SecureBot Memory & Continuity System

## Overview

SecureBot's memory system provides persistent context, continuity across sessions, and system-native automation. The architecture follows the Unix philosophy: **use system tools first, build custom solutions only when necessary**.

## Three-Layer Memory Architecture

### 1. Identity Layer (`soul.md`)
**Purpose:** Define what SecureBot IS - core identity, values, capabilities

- **Never auto-modified** - protected as read-only (chmod 444)
- Contains SecureBot's purpose, values, and behavioral guidelines
- Includes automation philosophy and architectural principles
- Updated manually only when fundamental changes occur

**Contents:**
- Core identity and purpose
- Values and principles
- Automation philosophy (system-native tools first)
- Capability matrix
- Behavioral guidelines
- Creator attribution

### 2. User Layer (`user.md`)
**Purpose:** Know WHO we're working with - preferences, expertise, goals

- User profile and technical background
- Communication style preferences
- Current projects and goals
- Hardware configuration
- Automation expertise
- Preferences (language, tools, cost targets)

**Contents:**
- Identity and role
- Technical background and expertise
- Current projects
- Short/medium/long-term goals
- Communication style
- Hardware specs
- Tool preferences

### 3. Session Layer (`session.md`)
**Purpose:** Track WHAT we're doing - current context, recent work

- Current session ID and timestamp
- Active task and recent work
- Recent decisions and open threads
- Context for next session
- Updated after each interaction

**Contents:**
- Session ID (UUID)
- Started timestamp
- Current task description
- Recent decisions made
- Open threads and pending work
- Context summary for next session

### 4. Task Layer (`tasks.json`)
**Purpose:** Manage TODO lists and completed work

- Structured JSON task tracking
- todo[] array for pending tasks
- completed[] array for finished tasks
- Task metadata (ID, title, description, priority, timestamps)

## System-Native Automation Philosophy

### The Golden Rule: Use System Tools First

**Before writing Python code, ask:**
1. Can **cron** handle this? (scheduled tasks)
2. Can **systemd** handle this? (services, timers, dependencies)
3. Can **bash** handle this? (simple automation)
4. Can **inotifywait** handle this? (file watching)
5. Can **ansible** handle this? (multi-machine)
6. Only then consider Python

### Why System-Native Tools?

**Advantages:**
- **More reliable**: Battle-tested for decades
- **Lower resource usage**: No Python interpreter overhead
- **Better integration**: Native logging, service management
- **Easier debugging**: Standard tools everyone knows
- **Automatic recovery**: systemd auto-restart, cron retry
- **Persistent**: Survive reboots, handle missed executions

**Example: Heartbeat**
❌ **Wrong**: Python service with `asyncio.sleep(300)` loop
✅ **Right**: systemd timer running every 5 minutes

## Heartbeat System

### Architecture

The heartbeat system uses **systemd timers** instead of Python sleep loops:

```
┌─────────────────────────────────────────┐
│   systemd Timer (Every 5 minutes)       │
│   securebot-heartbeat.timer              │
└────────────────┬────────────────────────┘
                 │ triggers
                 ▼
┌─────────────────────────────────────────┐
│   systemd Service (One-shot)             │
│   securebot-heartbeat.service            │
└────────────────┬────────────────────────┘
                 │ executes
                 ▼
┌─────────────────────────────────────────┐
│   Bash Script                            │
│   heartbeat.sh                           │
│   - Keep Ollama warm                     │
│   - Update session timestamp             │
│   - Check service health                 │
│   - Auto-restart if needed               │
└─────────────────────────────────────────┘
```

### Components

**1. systemd Timer** (`securebot-heartbeat.timer`)
```ini
[Timer]
OnBootSec=2min          # Run 2 min after boot
OnUnitActiveSec=5min    # Run every 5 min after last activation
AccuracySec=30s         # Allow 30s drift for power savings
```

**2. systemd Service** (`securebot-heartbeat.service`)
```ini
[Service]
Type=oneshot            # Run once and exit
ExecStart=/path/to/heartbeat.sh
```

**3. Bash Script** (`heartbeat.sh`)
- Keep Ollama warm (prevent cold starts)
- Update session last_active timestamp
- Check Docker container health
- Auto-restart failed services
- Log all activities

### Additional Timers

**Hourly Summary** (`securebot-hourly.timer`)
- System stats (CPU, RAM, disk)
- Container health status
- Ollama model status
- Logs to `memory/hourly.log`

**Daily Report** (`securebot-daily.timer`)
- Archive previous session
- Create new session for today
- Task statistics
- Cost summary (TODO)
- Logs to `memory/daily.log`

### Log Rotation

Uses **logrotate** (system native):
```
/home/tasker0/securebot/memory/*.log {
    daily           # Rotate daily
    rotate 7        # Keep 7 days
    compress        # Compress old logs
    missingok       # Don't error if missing
    notifempty      # Don't rotate empty logs
}
```

## Memory Service (Minimal Python)

### Design Principle
**Only use Python when system tools insufficient**

The memory service is a minimal FastAPI app that:
- Reads/writes memory files
- Provides REST API for file access
- NO complex logic, NO sleep loops, NO business logic
- Just a simple file API

### Endpoints

#### Health
- `GET /health` - Service health check

#### Memory Files
- `GET /memory/soul` - Read soul.md
- `GET /memory/user` - Read user.md
- `GET /memory/session` - Read session.md
- `POST /memory/session` - Update session fields
- `GET /memory/context` - Combined context for Ollama

#### Tasks
- `GET /tasks` - Get all tasks
- `POST /tasks` - Create new task
- `PUT /tasks/{id}` - Update task
- `POST /tasks/{id}/complete` - Mark completed

#### Logs
- `GET /memory/heartbeat` - Last 50 heartbeat log lines

### Integration with Gateway

The gateway orchestrator:
1. Loads memory context from memory service
2. Prepends context to Ollama prompts
3. Graceful fallback if memory service unavailable
4. Updates session after interactions

**Context Injection:**
```python
# Load memory context
memory_context = await load_memory_context()

# Prepend to prompt
final_prompt = f"{memory_context}\n\n---\n\n{user_query}"

# Send to Ollama
result = ollama.generate(model="phi4-mini:3.8b", prompt=final_prompt)
```

This gives Ollama awareness of:
- SecureBot's identity and purpose
- User preferences and background
- Current session context
- Recent decisions and work

## Automation Skills

SecureBot includes five automation skills that teach how to use system-native tools:

### 1. cron-manager
**When to use:** Schedule recurring tasks (backups, reports, cleanup)

**What it teaches:**
- Cron syntax and patterns
- Common scheduling examples
- Best practices for cron jobs
- Troubleshooting cron issues

**Example use cases:**
- Daily backups at 2am
- Hourly log processing
- Weekly report generation
- Periodic cleanup tasks

### 2. systemd-service
**When to use:** Run programs as persistent background services

**What it teaches:**
- Service unit file structure
- Service types (simple, forking, oneshot)
- Restart policies
- Dependency management
- Logging with journald

**Example use cases:**
- Docker Compose as service
- Python/Node.js apps as services
- Auto-restart on failure
- Start on boot

### 3. systemd-timer
**When to use:** Modern replacement for cron with better features

**What it teaches:**
- Timer unit file structure
- Calendar vs relative scheduling
- Persistent timers (catch up missed runs)
- Integration with services

**Example use cases:**
- Complex scheduling requirements
- Tasks with service dependencies
- Persistent scheduled tasks
- Better logging needs

### 4. bash-automation
**When to use:** Create automation scripts for system tasks

**What it teaches:**
- Bash script structure and best practices
- Common automation patterns
- Error handling and logging
- System monitoring scripts

**Example use cases:**
- Service health checks
- Backup scripts
- Log processing
- File cleanup
- System monitoring

### 5. ansible-playbook
**When to use:** Multi-machine automation and configuration management

**What it teaches:**
- Playbook structure
- Inventory management
- Common modules
- Idempotent operations
- Roles and organization

**Example use cases:**
- Deploy to multiple servers
- Configuration management
- Application deployment
- Infrastructure setup

## Installation

### 1. Install systemd Units
```bash
# Run as root
sudo bash /home/tasker0/securebot/services/scripts/install_systemd.sh
```

This installs:
- `securebot-memory.service` - Memory service
- `securebot-heartbeat.timer` - Every 5 minutes
- `securebot-hourly.timer` - Hourly summary
- `securebot-daily.timer` - Daily report

### 2. Install Logrotate Config
```bash
# Run as root
sudo bash /home/tasker0/securebot/services/config/install_logrotate.sh
```

### 3. Start Docker Services
```bash
cd /home/tasker0/securebot
docker compose up -d
```

## Monitoring

### Check Timer Status
```bash
# List all SecureBot timers
systemctl list-timers securebot-*

# Check specific timer
systemctl status securebot-heartbeat.timer
```

### View Logs
```bash
# Heartbeat log
tail -f /home/tasker0/securebot/memory/heartbeat.log

# Hourly summary
tail -f /home/tasker0/securebot/memory/hourly.log

# Daily report
tail -f /home/tasker0/securebot/memory/daily.log

# systemd journal
journalctl -u securebot-heartbeat.service -f
```

### Check Service Health
```bash
# Memory service
curl http://localhost:8300/health

# Gateway
curl http://localhost:8080/health

# Vault
curl http://localhost:8200/health
```

## Decision Guide: When to Use What

### Scheduled Tasks

| Requirement | Tool | Why |
|-------------|------|-----|
| Simple schedule (daily, hourly) | **cron** | Simplest, universal |
| Complex schedule | **systemd timer** | Better control |
| Needs service dependencies | **systemd timer** | Built-in After=/Requires |
| Must catch up missed runs | **systemd timer** | Persistent=true |
| Need detailed logs | **systemd timer** | journald integration |

### Background Services

| Requirement | Tool | Why |
|-------------|------|-----|
| Long-running service | **systemd service** | Auto-restart, logging |
| Docker containers | **systemd service** | Better than docker restart |
| One-time tasks | **systemd oneshot** | With timers for schedule |
| Python/Node apps | **systemd service** | Process management |

### File Operations

| Requirement | Tool | Why |
|-------------|------|-----|
| Watch for file changes | **inotifywait** | Native, efficient |
| Backup files | **rsync + cron** | Incremental, reliable |
| Rotate logs | **logrotate** | Standard, automatic |
| Compress old files | **find + gzip + cron** | Built-in tools |

### Multi-Machine

| Requirement | Tool | Why |
|-------------|------|-----|
| Deploy to multiple servers | **ansible** | Idempotent, declarative |
| Configure many machines | **ansible** | Configuration management |
| Orchestrate complex deployments | **ansible** | Roles, dependencies |

### Custom Logic

| Requirement | Tool | Why |
|-------------|------|-----|
| Simple automation | **bash script** | Fast, no dependencies |
| Complex logic | **Python** | When bash insufficient |
| API needed | **FastAPI** | When REST API needed |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    SecureBot Memory System                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   soul.md    │  │   user.md    │  │ session.md   │  Memory Files
│  (identity)  │  │  (profile)   │  │  (context)   │  (read-only soul)
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Memory Service      │  FastAPI
              │  (port 8300)         │  Minimal Python
              │  - File read/write   │  REST API
              │  - Task management   │
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Gateway             │  Orchestrator
              │  (port 8080)         │  Loads context
              │  - Load memory       │  Injects into
              │  - Inject context    │  Ollama prompts
              └──────────┬───────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │  Ollama              │  Local LLM
              │  (phi4-mini:3.8b)    │  With context
              └──────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   Systemd Automation Layer                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ heartbeat.timer  │   │  hourly.timer    │   │  daily.timer     │
│  (every 5 min)   │   │  (every hour)    │   │  (daily)         │
└────────┬─────────┘   └────────┬─────────┘   └────────┬─────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│ heartbeat.sh     │   │hourly_summary.sh │   │daily_report.sh   │
│ - Warm Ollama    │   │ - System stats   │   │ - Archive session│
│ - Update session │   │ - Container check│   │ - Reset session  │
│ - Check services │   │ - Model status   │   │ - Task summary   │
└──────────────────┘   └──────────────────┘   └──────────────────┘
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Log Files                                 │
│  heartbeat.log  |  hourly.log  |  daily.log                  │
│                                                               │
│  ┌──────────────────────────────────────┐                    │
│  │  Logrotate (daily, keep 7 days)     │                    │
│  └──────────────────────────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

## Future Enhancements

### Cost Tracking
- Track Claude API usage per session
- Daily cost summaries in daily report
- Budget alerts when approaching limit

### Smart Context Loading
- Load only relevant memory sections
- Context size optimization
- Time-decay for old context

### Multi-User Support
- Per-user memory directories
- User-specific soul/session files
- Isolated task lists

### Advanced Automation
- File watching with inotifywait skills
- Ansible playbook generator skill
- System monitoring dashboards

## Summary

SecureBot's memory system demonstrates that **modern AI assistants don't need to reinvent the wheel**. By leveraging battle-tested system tools (systemd, cron, bash, logrotate), we achieve:

✅ **Reliability** - Decades of proven stability
✅ **Efficiency** - Lower resource usage
✅ **Maintainability** - Standard tools everyone knows
✅ **Recovery** - Automatic restart and error handling
✅ **Logging** - Native integration with journald/syslog
✅ **Persistence** - Survive reboots, catch up missed runs

**The Unix philosophy applies to AI systems too**: Do one thing well, compose tools together, prefer text streams, and avoid unnecessary complexity.
