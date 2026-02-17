---
name: bash-automation
description: Generate bash scripts for system automation, file management, service monitoring, backup tasks, and general Linux administration. Use for automation scripts, monitoring, backups, system maintenance, log processing, file operations, service checks.
triggers: ["automate", "script", "bash", "shell", "monitor", "backup", "maintenance", "log processing"]
category: automation
execution: claude-code
allowed-tools: ["Bash(*)", "Read", "Write"]
---

# Bash Automation Script Generator

Creates bash scripts for system automation and administration tasks.

## When to Use
- Automate repetitive system tasks
- Create monitoring scripts
- Build backup solutions
- Process logs and files
- Check service health
- Perform system maintenance
- Orchestrate multiple commands
- Create installation scripts

## Script Template

### Basic Structure
```bash
#!/bin/bash
# Script Name: script_name.sh
# Description: What this script does
# Author: SecureBot
# Date: YYYY-MM-DD

set -euo pipefail  # Exit on error, undefined vars, pipe failures
IFS=$'\n\t'        # Better word splitting

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/script_name.log"

# Functions
log() {
    echo "[$(date -Iseconds)] $1" | tee -a "$LOG_FILE"
}

error() {
    echo "[$(date -Iseconds)] ERROR: $1" >&2 | tee -a "$LOG_FILE"
    exit 1
}

# Main script
main() {
    log "Script started"

    # Your code here

    log "Script completed"
}

# Run main function
main "$@"
```

## Common Automation Patterns

### Service Health Check
```bash
#!/bin/bash
# Check if service is running and restart if needed

SERVICE_NAME="myservice"
LOG_FILE="/var/log/health_check.log"

check_service() {
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        echo "[$(date -Iseconds)] $SERVICE_NAME: healthy" >> "$LOG_FILE"
        return 0
    else
        echo "[$(date -Iseconds)] $SERVICE_NAME: down - restarting" >> "$LOG_FILE"
        systemctl restart "$SERVICE_NAME"
        sleep 5
        if systemctl is-active --quiet "$SERVICE_NAME"; then
            echo "[$(date -Iseconds)] $SERVICE_NAME: restart successful" >> "$LOG_FILE"
        else
            echo "[$(date -Iseconds)] $SERVICE_NAME: restart failed!" >> "$LOG_FILE"
            # Send alert (email, slack, etc.)
        fi
    fi
}

check_service
```

### Backup Script
```bash
#!/bin/bash
# Backup files with rotation

SOURCE_DIR="/home/user/data"
BACKUP_DIR="/backup"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backup_$TIMESTAMP.tar.gz"

# Create backup
tar -czf "$BACKUP_DIR/$BACKUP_FILE" "$SOURCE_DIR" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "[$(date)] Backup successful: $BACKUP_FILE"

    # Remove old backups
    find "$BACKUP_DIR" -name "backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete
    echo "[$(date)] Old backups removed (>$RETENTION_DAYS days)"
else
    echo "[$(date)] Backup failed!" >&2
    exit 1
fi
```

### Log Processing
```bash
#!/bin/bash
# Extract errors from logs and send summary

LOG_FILE="/var/log/application.log"
ERROR_COUNT=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo 0)
TIMESTAMP=$(date +%Y-%m-%d)

if [ "$ERROR_COUNT" -gt 0 ]; then
    echo "=== Error Summary for $TIMESTAMP ==="
    echo "Total errors: $ERROR_COUNT"
    echo ""
    echo "Recent errors:"
    grep "ERROR" "$LOG_FILE" | tail -10

    # Could send email or Slack notification here
fi
```

### File Cleanup
```bash
#!/bin/bash
# Clean up old files and logs

TEMP_DIR="/tmp"
LOG_DIR="/var/log/app"
DAYS_OLD=7

echo "[$(date)] Starting cleanup..."

# Remove old temp files
DELETED=$(find "$TEMP_DIR" -type f -mtime +$DAYS_OLD -delete -print | wc -l)
echo "Removed $DELETED temp files older than $DAYS_OLD days"

# Compress old logs
find "$LOG_DIR" -name "*.log" -mtime +1 -exec gzip {} \;
echo "Compressed old log files"

# Remove compressed logs older than retention
find "$LOG_DIR" -name "*.log.gz" -mtime +$DAYS_OLD -delete
echo "Removed old compressed logs"

echo "[$(date)] Cleanup complete"
```

### System Monitoring
```bash
#!/bin/bash
# Monitor system resources and alert if thresholds exceeded

CPU_THRESHOLD=80
MEM_THRESHOLD=80
DISK_THRESHOLD=90

check_cpu() {
    CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    if (( $(echo "$CPU_USAGE > $CPU_THRESHOLD" | bc -l) )); then
        echo "WARNING: CPU usage at ${CPU_USAGE}%"
    fi
}

check_memory() {
    MEM_USAGE=$(free | grep Mem | awk '{print ($3/$2) * 100}' | cut -d'.' -f1)
    if [ "$MEM_USAGE" -gt "$MEM_THRESHOLD" ]; then
        echo "WARNING: Memory usage at ${MEM_USAGE}%"
    fi
}

check_disk() {
    df -h | grep -vE '^Filesystem|tmpfs|cdrom' | while read line; do
        USAGE=$(echo "$line" | awk '{print $5}' | cut -d'%' -f1)
        MOUNT=$(echo "$line" | awk '{print $6}')
        if [ "$USAGE" -gt "$DISK_THRESHOLD" ]; then
            echo "WARNING: Disk usage at ${USAGE}% on $MOUNT"
        fi
    done
}

check_cpu
check_memory
check_disk
```

### Database Backup
```bash
#!/bin/bash
# Backup PostgreSQL database

DB_NAME="mydb"
DB_USER="dbuser"
BACKUP_DIR="/backup/db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_$TIMESTAMP.sql.gz"
RETENTION_DAYS=14

# Create backup directory if needed
mkdir -p "$BACKUP_DIR"

# Perform backup
pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "[$(date)] Database backup successful: $BACKUP_FILE"

    # Remove old backups
    find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +$RETENTION_DAYS -delete
else
    echo "[$(date)] Database backup failed!" >&2
    exit 1
fi
```

### Docker Container Monitor
```bash
#!/bin/bash
# Monitor Docker containers and restart if unhealthy

CONTAINERS=("container1" "container2" "container3")

for container in "${CONTAINERS[@]}"; do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null)

    if [ "$STATUS" != "running" ]; then
        echo "[$(date)] Container $container is $STATUS - restarting"
        docker restart "$container"
    else
        echo "[$(date)] Container $container: healthy"
    fi
done
```

### API Health Check
```bash
#!/bin/bash
# Check API endpoints and alert if down

ENDPOINTS=(
    "http://localhost:8080/health"
    "http://localhost:8200/health"
    "http://localhost:8300/health"
)

for endpoint in "${ENDPOINTS[@]}"; do
    if curl -sf "$endpoint" > /dev/null 2>&1; then
        echo "[$(date)] $endpoint: healthy"
    else
        echo "[$(date)] WARNING: $endpoint is unreachable!"
        # Could send alert here
    fi
done
```

## Best Practices

### Error Handling
```bash
# Exit on error
set -e

# Exit on undefined variable
set -u

# Exit on pipe failure
set -o pipefail

# All at once
set -euo pipefail
```

### Logging
```bash
# Simple logging
log() {
    echo "[$(date -Iseconds)] $1" | tee -a "$LOG_FILE"
}

# With severity levels
log_info() {
    echo "[$(date -Iseconds)] INFO: $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date -Iseconds)] ERROR: $1" | tee -a "$LOG_FILE" >&2
}
```

### Locking (Prevent Concurrent Runs)
```bash
LOCK_FILE="/var/run/myscript.lock"

# Acquire lock
exec 200>"$LOCK_FILE"
flock -n 200 || { echo "Script already running"; exit 1; }

# Your script here

# Lock released automatically on exit
```

### Configuration Files
```bash
# Load config from file
CONFIG_FILE="/etc/myscript.conf"
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi
```

### Command Line Arguments
```bash
usage() {
    echo "Usage: $0 [-h] [-v] [-f FILE]"
    exit 1
}

while getopts "hvf:" opt; do
    case $opt in
        h) usage ;;
        v) VERBOSE=1 ;;
        f) FILE="$OPTARG" ;;
        *) usage ;;
    esac
done
```

### Cleanup on Exit
```bash
cleanup() {
    echo "Cleaning up..."
    # Remove temp files, unlock, etc.
}

trap cleanup EXIT
```

## Useful Commands

### File Operations
```bash
# Find and process files
find /path -name "*.log" -mtime +7 -exec gzip {} \;

# Recursive search and replace
find . -type f -name "*.txt" -exec sed -i 's/old/new/g' {} \;

# Copy with progress
rsync -avh --progress /source/ /dest/
```

### Text Processing
```bash
# Extract specific columns
awk '{print $1, $3}' file.txt

# Filter and count
grep "ERROR" log.txt | wc -l

# Sort and unique
sort file.txt | uniq -c
```

### System Info
```bash
# CPU usage
top -bn1 | grep "Cpu(s)"

# Memory usage
free -h

# Disk usage
df -h

# Process info
ps aux | grep process_name
```

## Testing Scripts
```bash
# Check syntax
bash -n script.sh

# Run with trace
bash -x script.sh

# Verbose mode
bash -v script.sh
```

## Making Scripts Executable
```bash
# Add execute permission
chmod +x script.sh

# Run script
./script.sh
```

## Scheduling Scripts
- Use cron for simple schedules
- Use systemd timers for complex schedules
- See cron-manager and systemd-timer skills

## Related Skills
- cron-manager: Schedule bash scripts with cron
- systemd-timer: Schedule bash scripts with systemd
- systemd-service: Run bash scripts as services
- ansible-playbook: Multi-machine automation
