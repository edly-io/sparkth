"""
Example Tasks Plugin - Demonstrates plugin with database models

This plugin shows how to:
1. Define SQLModel models
2. Register them for migrations
3. Add API endpoints for the models
4. Use the plugin migration system

To use this plugin:
1. Copy to sparkth-plugins/: cp examples/tasks_plugin.py sparkth-plugins/
2. Enable: sparkth plugins enable tasks_plugin
3. Generate migration: sparkth plugins migrate create tasks_plugin "add Task model"
4. Apply migration: sparkth plugins migrate apply
5. Start server: uvicorn app.main:app --reload
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import SQLModel, Field, Session, select

from app.hooks.catalog import Actions, Filters
from app.core.db import get_session  # Assuming you have this

# Plugin metadata
__version__ = "1.0.0"
__description__ = "Task management plugin with database models"


# ============================================================================
# DATABASE MODELS
# ============================================================================

class Task(SQLModel, table=True):
    """Task model for the plugin."""
    
    __tablename__ = "tasks_plugin_tasks"  # Namespaced table name
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=255)
    description: Optional[str] = None
    completed: bool = Field(default=False)
    priority: int = Field(default=1, ge=1, le=5)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Foreign key to user table (if exists)
    # user_id: Optional[int] = Field(default=None, foreign_key="user.id")


# Register model for migration discovery
Filters.SQLMODEL_MODELS.add_item(Task)


# ============================================================================
# API ENDPOINTS
# ============================================================================

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/")
async def list_tasks(
    completed: Optional[bool] = None,
    session: Session = Depends(get_session)
):
    """List all tasks with optional filtering."""
    query = select(Task)
    
    if completed is not None:
        query = query.where(Task.completed == completed)
    
    tasks = session.exec(query).all()
    return {"tasks": tasks}


@router.post("/")
async def create_task(
    title: str,
    description: Optional[str] = None,
    priority: int = 1,
    session: Session = Depends(get_session)
):
    """Create a new task."""
    task = Task(
        title=title,
        description=description,
        priority=priority
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.get("/{task_id}")
async def get_task(task_id: int, session: Session = Depends(get_session)):
    """Get a specific task by ID."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}")
async def update_task(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    completed: Optional[bool] = None,
    priority: Optional[int] = None,
    session: Session = Depends(get_session)
):
    """Update a task."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if completed is not None:
        task.completed = completed
    if priority is not None:
        task.priority = priority
    
    task.updated_at = datetime.utcnow()
    
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: int, session: Session = Depends(get_session)):
    """Delete a task."""
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    session.delete(task)
    session.commit()
    return {"message": "Task deleted successfully"}


# Register the router
Filters.API_ROUTERS.add_item(("tasks", router))


# ============================================================================
# LIFECYCLE HOOKS
# ============================================================================

@Actions.APP_STARTUP.add()
def on_startup():
    """Called when the application starts."""
    print(f"Tasks plugin v{__version__} initialized!")
    print(f"API endpoints available at /plugins/tasks/")


@Actions.APP_SHUTDOWN.add()
def on_shutdown():
    """Called when the application shuts down."""
    print("Tasks plugin shutting down...")


# Add configuration defaults
Filters.CONFIG_DEFAULTS.add_items([
    ("TASKS_PLUGIN_MAX_PER_USER", 100),
    ("TASKS_PLUGIN_ENABLE_NOTIFICATIONS", True),
])


@Actions.PLUGIN_LOADED.add()
def on_plugin_loaded(plugin_name: str):
    """Called when any plugin is loaded."""
    if plugin_name == "tasks_plugin":
        print("✓ Tasks plugin loaded successfully!")
        print("  Database model: Task")
        print("  Table: tasks_plugin_tasks")
