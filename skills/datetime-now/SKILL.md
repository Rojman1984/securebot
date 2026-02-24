---
name: datetime-now
description: Returns the current system date and time from the host OS
triggers:
  - what time is it
  - what's the time
  - current time
  - what day is it
  - today's date
  - what's today
  - current date
  - date and time
  - what year is it
  - what month is it
execution_mode: bash
timeout: 5
---

# Datetime Now

## Purpose
Returns the current system date, time, and timezone from the host OS.
Executes a bash command and returns the output to the model for natural
language wrapping.

## Script
```bash
#!/bin/bash
date '+%A, %B %d, %Y at %I:%M %p %Z'
```

## Output Format
The script outputs a single line:
  Saturday, February 21, 2026 at 11:45 PM CST

The model wraps this in natural language:
  "It's Saturday, February 21, 2026 at 11:45 PM CST."

## Examples
User: "What time is it?"
Script output: Saturday, February 21, 2026 at 11:45 PM CST
Response: It's Saturday, February 21, 2026 at 11:45 PM CST.

User: "What's today's date?"
Script output: Saturday, February 21, 2026 at 11:45 PM CST
Response: Today is Saturday, February 21, 2026.
