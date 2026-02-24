---
name: remove-completed-tasks
description: Mark tasks as completed and remove them from pending list
triggers:
  - those tasks are done
  - remove them from pendings
  - mark tasks as completed
  - remove completed tasks
execution_mode: ollama
model: llama3.2:3b
---

# Remove Completed Tasks

## Purpose
This skill acknowledges that specified tasks have been completed and removes them from the pending task list. It provides confirmation of task completion and updates task status.

## Instructions
1. Identify which tasks the user is referring to as completed
2. Acknowledge each task that is being marked as done
3. Confirm removal from the pending list
4. Provide a summary of remaining pending tasks if applicable

## Output Format
Confirmation message listing completed tasks and their removal from pending status. Include count of tasks removed and any remaining pending items.

## Examples
User: Those tasks are done. You can remove them from pendings.
Response: I've marked the following tasks as completed and removed them from your pending list:
- Task 1: [description] ✓
- Task 2: [description] ✓

You now have X pending tasks remaining.