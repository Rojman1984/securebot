---
name: systemd-timer
description: Create systemd timers as a modern replacement for cron. Better than cron for dependency management, missed execution handling, logging via journald, and complex scheduling. Use for periodic tasks that need systemd integration.
triggers: ["timer", "systemd schedule", "periodic", "modern cron", "systemd cron"]
category: automation
execution: claude-code
allowed-tools: ["Bash(systemctl*)", "Read", "Write"]
---

# Systemd Timer Creator

Creates systemd timer units as a modern alternative to cron.

## When to Use
- Replace cron jobs with better integration
- Schedule tasks with dependency management
- Need persistent timers (survive missed executions)
- Want centralized logging via journald
- Complex scheduling requirements
- Need to wait for services before running

## Advantages Over Cron
- Dependency management (wait for services)
- Better logging (journald integration)
- Persistent timers (catch up missed runs)
- Can check last run time
- More flexible scheduling
- Easier debugging

## Timer Unit Structure

### Timer File (.timer)
```ini
[Unit]
Description=My Timer Description

[Timer]
OnCalendar=daily
Persistent=true
AccuracySec=1h

[Install]
WantedBy=timers.target
```

### Service File (.service)
```ini
[Unit]
Description=My Timer Task

[Service]
Type=oneshot
ExecStart=/path/to/command
```

## Scheduling Options

### OnCalendar (Calendar-based)
```ini
# Daily at midnight
OnCalendar=daily

# Hourly
OnCalendar=hourly

# Specific time
OnCalendar=*-*-* 02:30:00

# Multiple times
OnCalendar=Mon,Tue,Wed 09:00:00
OnCalendar=Thu,Fri 10:00:00

# Every 4 hours
OnCalendar=00/4:00:00

# Weekdays at 9am
OnCalendar=Mon-Fri 09:00:00
```

### OnUnitActiveSec (Relative to last activation)
```ini
# Every 5 minutes
OnUnitActiveSec=5min

# Every hour
OnUnitActiveSec=1h

# Every day
OnUnitActiveSec=1d
```

### OnBootSec (Relative to boot)
```ini
# 10 minutes after boot
OnBootSec=10min
```

### OnStartupSec (Relative to systemd start)
```ini
# 5 minutes after systemd starts
OnStartupSec=5min
```

## Implementation Steps

### 1. Create Service Unit
```bash
sudo nano /etc/systemd/system/mytask.service
```

```ini
[Unit]
Description=My Scheduled Task

[Service]
Type=oneshot
User=myuser
ExecStart=/home/myuser/scripts/task.sh
```

### 2. Create Timer Unit
```bash
sudo nano /etc/systemd/system/mytask.timer
```

```ini
[Unit]
Description=Run My Task Daily

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
```

### 3. Reload Systemd
```bash
sudo systemctl daemon-reload
```

### 4. Enable and Start Timer
```bash
sudo systemctl enable --now mytask.timer
```

### 5. Verify Timer
```bash
systemctl status mytask.timer
systemctl list-timers
```

## Common Timer Patterns

### Hourly Task
```ini
[Timer]
OnCalendar=hourly
Persistent=true
```

### Daily at Specific Time
```ini
[Timer]
OnCalendar=*-*-* 02:30:00
Persistent=true
```

### Every N Minutes
```ini
[Timer]
OnBootSec=5min
OnUnitActiveSec=5min
```

### Weekday Schedule
```ini
[Timer]
OnCalendar=Mon-Fri 09:00:00
Persistent=true
```

### Multiple Times Per Day
```ini
[Timer]
OnCalendar=*-*-* 08:00:00
OnCalendar=*-*-* 12:00:00
OnCalendar=*-*-* 18:00:00
Persistent=true
```

## Real-World Examples

### Backup Timer
```ini
# /etc/systemd/system/backup.timer
[Unit]
Description=Daily Backup Timer

[Timer]
OnCalendar=02:00:00
Persistent=true
AccuracySec=10min

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/backup.service
[Unit]
Description=Backup Task
After=network.target

[Service]
Type=oneshot
User=backup
ExecStart=/home/backup/scripts/backup.sh
```

### System Health Check
```ini
# /etc/systemd/system/healthcheck.timer
[Unit]
Description=System Health Check Every 15 Minutes

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min

[Install]
WantedBy=timers.target
```

```ini
# /etc/systemd/system/healthcheck.service
[Unit]
Description=Health Check Task

[Service]
Type=oneshot
ExecStart=/usr/local/bin/healthcheck.sh
```

### Log Cleanup
```ini
# /etc/systemd/system/log-cleanup.timer
[Unit]
Description=Clean Old Logs Weekly

[Timer]
OnCalendar=Sun 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

## Timer Options

### Persistent
```ini
# Run missed executions on boot
Persistent=true
```

### AccuracySec
```ini
# Allow timer to drift within 1 hour (save power)
AccuracySec=1h

# Require accurate timing (default: 1min)
AccuracySec=1s
```

### RandomizedDelaySec
```ini
# Spread load - random delay up to 1 hour
RandomizedDelaySec=1h
```

### OnClockChange / OnTimezoneChange
```ini
# Trigger on clock/timezone change
OnClockChange=yes
OnTimezoneChange=yes
```

## Managing Timers

### List All Timers
```bash
systemctl list-timers --all
```

### Start/Stop Timer
```bash
sudo systemctl start mytask.timer
sudo systemctl stop mytask.timer
```

### Enable/Disable Timer
```bash
sudo systemctl enable mytask.timer
sudo systemctl disable mytask.timer
```

### Check Timer Status
```bash
systemctl status mytask.timer
```

### View Last Run
```bash
journalctl -u mytask.service -n 20
```

### Manually Trigger Service
```bash
sudo systemctl start mytask.service
```

## Calendar Format Reference
```
Syntax: DayOfWeek Year-Month-Day Hour:Minute:Second

Examples:
*-*-* 00:00:00        - Daily at midnight
*-*-01 00:00:00       - Monthly on 1st
Mon *-*-* 00:00:00    - Every Monday
Mon-Fri 09:00:00      - Weekdays at 9am
*-*-* 00/6:00:00      - Every 6 hours
```

## Troubleshooting

### Check Timer Next Run
```bash
systemctl list-timers mytask.timer
```

### View Timer Logs
```bash
journalctl -u mytask.timer
journalctl -u mytask.service
```

### Test Service Manually
```bash
sudo systemctl start mytask.service
sudo systemctl status mytask.service
```

### Verify Timer Configuration
```bash
systemd-analyze calendar "Mon-Fri 09:00:00"
```

### Debug Why Timer Didn't Run
```bash
# Check timer status
systemctl status mytask.timer

# Check service status
systemctl status mytask.service

# Check logs
journalctl -u mytask -n 50
```

## Best Practices
- Use Type=oneshot for timer services
- Enable Persistent=true for important tasks
- Use AccuracySec for non-critical timers (saves power)
- Test service manually before enabling timer
- Use After= in service for dependencies
- Log output to syslog or file
- Set reasonable User (not root if possible)

## Calendar Syntax Testing
```bash
# Test calendar expressions
systemd-analyze calendar "Mon,Tue *-*-01..07 12:00:00"
systemd-analyze calendar daily
systemd-analyze calendar hourly
systemd-analyze calendar "Mon-Fri 09:00:00"
```

## Removing Timers
```bash
# Stop and disable
sudo systemctl stop mytask.timer
sudo systemctl disable mytask.timer

# Remove files
sudo rm /etc/systemd/system/mytask.timer
sudo rm /etc/systemd/system/mytask.service

# Reload
sudo systemctl daemon-reload
```

## Related Skills
- cron-manager: Simpler alternative for basic scheduling
- systemd-service: Long-running services vs scheduled tasks
- bash-automation: Create scripts for timers to execute
