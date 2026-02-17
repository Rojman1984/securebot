---
name: cron-manager
description: Add, remove, list, and manage cron jobs for automation tasks. Use when user wants to schedule recurring tasks, set up automation, run scripts periodically, schedule backups, or automate any time-based task.
triggers: ["schedule", "every hour", "daily", "cron", "automate", "recurring", "periodic", "run every"]
category: automation
execution: claude-code
allowed-tools: ["Bash(crontab*)", "Read", "Write"]
---

# Cron Job Manager

Manages cron jobs for task automation using the native Linux cron scheduler.

## When to Use
- Schedule recurring tasks (backups, reports, cleanup, etc.)
- Run scripts at specific times or intervals
- Automate time-based maintenance tasks
- Set up periodic data processing
- Schedule system checks and monitoring

## Cron Syntax Quick Reference
```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sun=0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

## Common Patterns
- Every 5 minutes: `*/5 * * * *`
- Every hour: `0 * * * *`
- Daily at midnight: `0 0 * * *`
- Daily at 2:30 AM: `30 2 * * *`
- Weekly on Sunday: `0 0 * * 0`
- Monthly on 1st: `0 0 1 * *`
- Weekdays at 9am: `0 9 * * 1-5`

## Implementation Steps

### 1. Understand Requirements
- What task needs to be scheduled?
- How frequently should it run?
- What time of day? (if applicable)
- Does the script already exist?

### 2. Create/Verify Script
- If script doesn't exist, create it
- Make it executable: `chmod +x script.sh`
- Test it manually first
- Ensure it uses absolute paths
- Add proper logging

### 3. Add to Crontab
```bash
# Edit user's crontab
crontab -e

# Or add directly
(crontab -l 2>/dev/null; echo "SCHEDULE COMMAND") | crontab -
```

### 4. Verify Installation
```bash
# List current cron jobs
crontab -l

# Check cron logs (if needed)
grep CRON /var/log/syslog
```

## Best Practices
- Always use absolute paths in cron jobs
- Redirect output to log files for debugging
- Test scripts manually before adding to cron
- Add comments to crontab entries
- Use environment variables at top of crontab if needed
- Consider using `flock` to prevent overlapping executions

## Example Cron Entries
```bash
# Backup database daily at 2am
0 2 * * * /home/user/scripts/backup_db.sh >> /var/log/backup.log 2>&1

# Clean temp files every 6 hours
0 */6 * * * find /tmp -type f -mtime +7 -delete

# System health check every 15 minutes
*/15 * * * * /home/user/scripts/health_check.sh

# Weekly report every Monday at 9am
0 9 * * 1 /home/user/scripts/weekly_report.sh
```

## Troubleshooting
- Check cron service: `systemctl status cron`
- View user's crontab: `crontab -l`
- Check logs: `grep CRON /var/log/syslog`
- Verify script permissions and paths
- Test script execution manually
- Ensure script has no interactive prompts

## Environment Notes
- Cron runs with minimal environment
- Set PATH explicitly if needed
- HOME, USER, LOGNAME are typically set
- Use `cd` in script if directory matters
- Export variables at top of crontab if needed

## Removing Cron Jobs
```bash
# Edit and remove manually
crontab -e

# Remove all cron jobs
crontab -r

# Remove specific job programmatically
crontab -l | grep -v "pattern" | crontab -
```

## Related Skills
- systemd-timer: Modern alternative to cron
- bash-automation: Create scripts for cron to run
- systemd-service: Long-running services vs scheduled tasks
