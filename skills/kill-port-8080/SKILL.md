---
name: kill-port-8080
description: Terminate the process running on port 8080
triggers:
  - kill port 8080
  - stop port 8080
  - kill process on 8080
execution_mode: bash
timeout: 10
---

# Kill Port 8080

## Purpose
Identifies and terminates the process currently using port 8080.

## Script
```bash
#!/bin/bash
PID=$(lsof -ti:8080)
if [ -z "$PID" ]; then
  echo "No process found on port 8080"
else
  kill -9 $PID
  echo "Process $PID on port 8080 has been terminated"
fi
```

## Output Format
Either confirms the PID of the terminated process, or reports that no process was found on port 8080.

## Examples
User: kill port 8080
Response: Process 1234 on port 8080 has been terminated

User: stop port 8080
Response: No process found on port 8080