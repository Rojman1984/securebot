---
name: systemd-service
description: Create and manage systemd services for running programs as background services with auto-restart, logging, and dependency management. Use when creating persistent background services, daemons, or processes that should survive reboots and auto-restart on failure.
triggers: ["service", "daemon", "background", "systemd", "auto-start", "on boot", "persistent service"]
category: automation
execution: claude-code
allowed-tools: ["Bash(systemctl*)", "Read", "Write"]
---

# Systemd Service Creator

Creates and manages systemd service units for background processes.

## When to Use
- Run programs as background services
- Auto-restart services on failure
- Start services on boot
- Manage dependencies between services
- Replace legacy init scripts
- Run Docker containers as services

## Service Unit Structure

### Basic Service Template
```ini
[Unit]
Description=My Service Description
After=network.target
Requires=some-other.service

[Service]
Type=simple
User=username
WorkingDirectory=/path/to/workdir
ExecStart=/path/to/command
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## Service Types
- `simple`: Default, process started is main process
- `forking`: Process forks and parent exits
- `oneshot`: Process expected to exit (use with timers)
- `notify`: Service sends notification when ready
- `dbus`: Service acquires D-Bus name

## Implementation Steps

### 1. Create Service File
```bash
sudo nano /etc/systemd/system/myservice.service
```

### 2. Write Service Configuration
```ini
[Unit]
Description=My Custom Service
After=network.target

[Service]
Type=simple
User=myuser
ExecStart=/usr/bin/python3 /home/myuser/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Reload Systemd
```bash
sudo systemctl daemon-reload
```

### 4. Enable and Start
```bash
# Enable (start on boot)
sudo systemctl enable myservice.service

# Start now
sudo systemctl start myservice.service

# Do both at once
sudo systemctl enable --now myservice.service
```

### 5. Verify Status
```bash
sudo systemctl status myservice.service
```

## Common Service Patterns

### Docker Compose Service
```ini
[Unit]
Description=My Docker App
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=myuser
WorkingDirectory=/home/myuser/app
ExecStart=/usr/bin/docker compose up
ExecStop=/usr/bin/docker compose down
Restart=always

[Install]
WantedBy=multi-user.target
```

### Python Application
```ini
[Unit]
Description=My Python App
After=network.target

[Service]
Type=simple
User=myuser
WorkingDirectory=/home/myuser/app
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Node.js Application
```ini
[Unit]
Description=My Node App
After=network.target

[Service]
Type=simple
User=nodeuser
WorkingDirectory=/home/nodeuser/app
ExecStart=/usr/bin/node server.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Restart Policies
- `no`: Never restart
- `always`: Always restart (even on clean exit)
- `on-failure`: Restart only on error exit
- `on-abnormal`: Restart on signals, timeout, watchdog
- `on-abort`: Restart only on unhandled signal

## Logging
```bash
# View service logs
journalctl -u myservice.service

# Follow logs in real-time
journalctl -u myservice.service -f

# Show recent logs
journalctl -u myservice.service -n 50

# Show logs since boot
journalctl -u myservice.service -b
```

## Service Management Commands
```bash
# Start service
sudo systemctl start myservice

# Stop service
sudo systemctl stop myservice

# Restart service
sudo systemctl restart myservice

# Reload config without restart
sudo systemctl reload myservice

# Enable on boot
sudo systemctl enable myservice

# Disable on boot
sudo systemctl disable myservice

# Check status
sudo systemctl status myservice

# Is service active?
systemctl is-active myservice

# Is service enabled?
systemctl is-enabled myservice
```

## Environment Variables
```ini
[Service]
Environment="VAR1=value1"
Environment="VAR2=value2"
EnvironmentFile=/etc/myservice/env
```

## Dependencies
```ini
[Unit]
# Start after these services
After=network.target postgresql.service

# Require these services (stop if they fail)
Requires=postgresql.service

# Want these services (don't stop if they fail)
Wants=redis.service

# Don't start with these services
Conflicts=other.service
```

## Security Options
```ini
[Service]
# Run as specific user/group
User=myuser
Group=mygroup

# Restrict capabilities
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

# Read-only root filesystem
ProtectSystem=strict

# Private /tmp
PrivateTmp=yes

# Deny write to /home, /root, /run
ProtectHome=yes
```

## Troubleshooting
```bash
# Check service status
systemctl status myservice

# View logs
journalctl -u myservice -n 100

# Verify unit file syntax
systemd-analyze verify /etc/systemd/system/myservice.service

# Show unit dependencies
systemctl list-dependencies myservice

# Reload daemon after editing
sudo systemctl daemon-reload
```

## Best Practices
- Always use absolute paths
- Set WorkingDirectory explicitly
- Use appropriate User (not root if possible)
- Set Restart policy for reliability
- Use After= for dependencies
- Test service manually before enabling
- Use EnvironmentFile for secrets
- Check logs after starting

## Removing Services
```bash
# Stop and disable
sudo systemctl stop myservice
sudo systemctl disable myservice

# Remove unit file
sudo rm /etc/systemd/system/myservice.service

# Reload daemon
sudo systemctl daemon-reload

# Reset failed state if needed
sudo systemctl reset-failed
```

## Related Skills
- systemd-timer: Scheduled tasks with systemd
- cron-manager: Alternative for simple scheduled tasks
- bash-automation: Create scripts to run as services
