"""
SecureBot Memory Service

Minimal FastAPI service for memory file management.
Just reads/writes memory files, no complex logic.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import json
import os

app = FastAPI(title="SecureBot Memory Service")

# Configuration
MEMORY_DIR = os.getenv("MEMORY_DIR", "/home/tasker0/securebot/memory")
SOUL_FILE = f"{MEMORY_DIR}/soul.md"
USER_FILE = f"{MEMORY_DIR}/user.md"
SESSION_FILE = f"{MEMORY_DIR}/session.md"
TASKS_FILE = f"{MEMORY_DIR}/tasks.json"
HEARTBEAT_LOG = f"{MEMORY_DIR}/heartbeat.log"


# Models
class SessionUpdate(BaseModel):
    """Model for updating session context"""
    last_active: Optional[str] = None
    current_task: Optional[str] = None
    recent_decisions: Optional[str] = None
    open_threads: Optional[str] = None
    context_for_next: Optional[str] = None


class TaskCreate(BaseModel):
    """Model for creating a new task"""
    title: str
    description: str
    priority: str = "medium"


class TaskUpdate(BaseModel):
    """Model for updating a task"""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None


# Utility functions
def read_file(filepath: str) -> str:
    """Read file contents"""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def write_file(filepath: str, content: str):
    """Write file contents"""
    try:
        with open(filepath, 'w') as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def read_json(filepath: str) -> Dict[str, Any]:
    """Read JSON file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {filepath}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def write_json(filepath: str, data: Dict[str, Any]):
    """Write JSON file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "memory", "timestamp": datetime.now().isoformat()}


# Memory endpoints
@app.get("/memory/soul")
async def get_soul():
    """Get SecureBot's soul/identity"""
    return {"content": read_file(SOUL_FILE)}


@app.get("/memory/user")
async def get_user():
    """Get user profile"""
    return {"content": read_file(USER_FILE)}


@app.get("/memory/session")
async def get_session():
    """Get current session context"""
    return {"content": read_file(SESSION_FILE)}


@app.post("/memory/session")
async def update_session(update: SessionUpdate):
    """Update session context fields"""
    try:
        content = read_file(SESSION_FILE)
        lines = content.split('\n')

        # Update specific fields if provided
        if update.last_active:
            # Update last_active by adding/updating timestamp in session
            # For simplicity, we'll just log this - full markdown parsing would be complex
            pass

        if update.current_task:
            # Find and update Current Task section
            in_task_section = False
            new_lines = []
            for i, line in enumerate(lines):
                if line.strip() == "## Current Task":
                    in_task_section = True
                    new_lines.append(line)
                    if i + 1 < len(lines):
                        new_lines.append(update.current_task)
                        # Skip old task line
                        continue
                elif in_task_section and line.startswith("##"):
                    in_task_section = False
                    new_lines.append(line)
                elif not in_task_section:
                    new_lines.append(line)

            content = '\n'.join(new_lines)
            write_file(SESSION_FILE, content)

        return {"status": "updated", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/context")
async def get_combined_context():
    """Get combined context for Ollama prompts"""
    try:
        soul = read_file(SOUL_FILE)
        user = read_file(USER_FILE)
        session = read_file(SESSION_FILE)

        context = f"""# SecureBot Context

{soul}

---

{user}

---

{session}
"""
        return {"content": context}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task endpoints
@app.get("/tasks")
async def get_tasks():
    """Get all tasks"""
    return read_json(TASKS_FILE)


@app.post("/tasks")
async def create_task(task: TaskCreate):
    """Add a new task"""
    try:
        tasks_data = read_json(TASKS_FILE)

        # Generate task ID
        todo_count = len(tasks_data.get("todo", []))
        completed_count = len(tasks_data.get("completed", []))
        task_id = f"task_{todo_count + completed_count + 1:03d}"

        # Create task object
        new_task = {
            "id": task_id,
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "created": datetime.now().isoformat(),
            "status": "pending"
        }

        # Add to todo list
        if "todo" not in tasks_data:
            tasks_data["todo"] = []
        tasks_data["todo"].append(new_task)

        # Update timestamp
        tasks_data["updated"] = datetime.now().isoformat()

        # Save
        write_json(TASKS_FILE, tasks_data)

        return {"status": "created", "task": new_task}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/tasks/{task_id}")
async def update_task(task_id: str, update: TaskUpdate):
    """Update a task"""
    try:
        tasks_data = read_json(TASKS_FILE)

        # Find task in todo list
        task_found = False
        for task in tasks_data.get("todo", []):
            if task["id"] == task_id:
                # Update fields
                if update.title:
                    task["title"] = update.title
                if update.description:
                    task["description"] = update.description
                if update.priority:
                    task["priority"] = update.priority
                if update.status:
                    task["status"] = update.status

                task_found = True
                break

        if not task_found:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Update timestamp
        tasks_data["updated"] = datetime.now().isoformat()

        # Save
        write_json(TASKS_FILE, tasks_data)

        return {"status": "updated", "task_id": task_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: str):
    """Mark task as completed and move to completed list"""
    try:
        tasks_data = read_json(TASKS_FILE)

        # Find and remove from todo
        task = None
        todo_list = tasks_data.get("todo", [])
        for i, t in enumerate(todo_list):
            if t["id"] == task_id:
                task = todo_list.pop(i)
                break

        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Update task
        task["status"] = "completed"
        task["completed"] = datetime.now().isoformat()

        # Add to completed list
        if "completed" not in tasks_data:
            tasks_data["completed"] = []
        tasks_data["completed"].append(task)

        # Update timestamp
        tasks_data["updated"] = datetime.now().isoformat()

        # Save
        write_json(TASKS_FILE, tasks_data)

        return {"status": "completed", "task": task}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/heartbeat")
async def get_heartbeat():
    """Get last 50 lines of heartbeat log"""
    try:
        with open(HEARTBEAT_LOG, 'r') as f:
            lines = f.readlines()
            last_lines = lines[-50:] if len(lines) > 50 else lines
            return {"lines": [line.strip() for line in last_lines]}
    except FileNotFoundError:
        return {"lines": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8300)
