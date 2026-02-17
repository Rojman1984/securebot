#!/bin/bash
# Daily report - cost summary, task review, log rotation

MEMORY_DIR="/home/tasker0/securebot/memory"
TIMESTAMP=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)

# Archive yesterday's session
if [ -f "$MEMORY_DIR/session.md" ]; then
    cp "$MEMORY_DIR/session.md" "$MEMORY_DIR/archive/session_$YESTERDAY.md" 2>/dev/null
fi

# Generate new session ID for today
NEW_SESSION_ID=$(uuidgen | tr '[:upper:]' '[:lower:]')
CURRENT_TIMESTAMP=$(date -Iseconds)

# Read current task from old session
CURRENT_TASK=$(grep -A1 "## Current Task" "$MEMORY_DIR/session.md" | tail -1 | sed 's/^[[:space:]]*//')

# Create new session for today
cat > "$MEMORY_DIR/session.md" << EOF
# Current Session

## Session ID
$NEW_SESSION_ID

## Started
$CURRENT_TIMESTAMP

## Current Task
$CURRENT_TASK

## Recent Decisions
(Carried over from previous session)

## Open Threads
(Carried over from previous session)

## Context for Next Session
New day started. Review yesterday's archive at: archive/session_$YESTERDAY.md
EOF

echo "[$CURRENT_TIMESTAMP] Daily report complete - Session archived and reset" >> "$MEMORY_DIR/daily.log"

# Count tasks from tasks.json
if [ -f "$MEMORY_DIR/tasks.json" ]; then
    TODO_COUNT=$(jq '.todo | length' "$MEMORY_DIR/tasks.json" 2>/dev/null || echo "0")
    COMPLETED_COUNT=$(jq '.completed | length' "$MEMORY_DIR/tasks.json" 2>/dev/null || echo "0")
    echo "Tasks: $TODO_COUNT pending, $COMPLETED_COUNT completed" >> "$MEMORY_DIR/daily.log"
fi

# Generate cost summary if available
# TODO: Implement cost tracking from gateway logs

echo "---" >> "$MEMORY_DIR/daily.log"
