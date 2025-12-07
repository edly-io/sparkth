# Plugin Database Migrations Guide

This guide explains how to add database models to your Sparkth plugins and manage migrations.

## Overview

The Sparkth plugin system integrates with Alembic to automatically handle database migrations for plugin models. This allows plugins to:

- Define their own database tables using SQLModel
- Generate migrations automatically
- Apply migrations during deployment
- Maintain schema versioning

## Quick Start

### 1. Define Models in Your Plugin

```python
# sparkth-plugins/my_plugin.py
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

from app.hooks.catalog import Filters

class MyModel(SQLModel, table=True):
    """Your plugin model."""
    
    # IMPORTANT: Use namespaced table name
    __tablename__ = "my_plugin_mymodels"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Register model for migrations
Filters.SQLMODEL_MODELS.add_item(MyModel)
```

### 2. Enable Your Plugin

```bash
sparkth plugins enable my_plugin
```

### 3. Generate Migration

```bash
sparkth plugins migrate create my_plugin "add MyModel table"
```

This will:
- Load your plugin
- Discover the registered models
- Generate an Alembic migration file in `app/migrations/versions/`
- Include your plugin name in the migration message

### 4. Apply Migration

```bash
sparkth plugins migrate apply
```

Or use standard Alembic:
```bash
alembic upgrade head
```

## Table Naming Convention

**CRITICAL**: All plugin tables MUST use namespaced names to avoid conflicts.

### ✅ Correct

```python
class Task(SQLModel, table=True):
    __tablename__ = "tasks_plugin_tasks"  # Prefixed with plugin name
```

### ❌ Wrong

```python
class Task(SQLModel, table=True):
    __tablename__ = "tasks"  # No prefix - will conflict!
```

### Naming Pattern

```
{plugin_name}_{model_name_plural}
```

Examples:
- `tasks_plugin_tasks`
- `calendar_plugin_events`
- `notifications_plugin_messages`

## Model Registration

### Register Single Model

```python
from app.hooks.catalog import Filters

Filters.SQLMODEL_MODELS.add_item(MyModel)
```

### Register Multiple Models

```python
Filters.SQLMODEL_MODELS.add_items([
    Task,
    TaskComment,
    TaskAttachment,
])
```

## CLI Commands

### Plugin Management

```bash
# List all plugins
sparkth plugins list

# Enable a plugin
sparkth plugins enable my_plugin

# Disable a plugin
sparkth plugins disable my_plugin

# Show plugin info
sparkth plugins info my_plugin
```

### Migration Commands

```bash
# List models for a plugin
sparkth plugins migrate models my_plugin

# List all plugin models
sparkth plugins migrate models

# Create migration for a plugin
sparkth plugins migrate create my_plugin "add new table"

# Apply all pending migrations
sparkth plugins migrate apply

# Rollback one migration
sparkth plugins migrate rollback

# Rollback multiple migrations
sparkth plugins migrate rollback --steps -2
```

## Complete Example: Tasks Plugin

```python
"""
Tasks Plugin with Database Models
File: sparkth-plugins/tasks_plugin.py
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from sqlmodel import SQLModel, Field, Session, select

from app.hooks.catalog import Actions, Filters
from app.core.db import get_session

# ============ Models ============

class Task(SQLModel, table=True):
    __tablename__ = "tasks_plugin_tasks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(max_length=255)
    description: Optional[str] = None
    completed: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Register for migrations
Filters.SQLMODEL_MODELS.add_item(Task)

# ============ API ============

router = APIRouter(prefix="/tasks")

@router.get("/")
async def list_tasks(session: Session = Depends(get_session)):
    tasks = session.exec(select(Task)).all()
    return {"tasks": tasks}

@router.post("/")
async def create_task(title: str, session: Session = Depends(get_session)):
    task = Task(title=title)
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

Filters.API_ROUTERS.add_item(("tasks", router))
```

## Workflow

### Development Workflow

1. **Create plugin with models**
   ```bash
   # Create plugin file
   touch sparkth-plugins/my_plugin.py
   # Edit and add models
   ```

2. **Enable plugin**
   ```bash
   sparkth plugins enable my_plugin
   ```

3. **Generate migration**
   ```bash
   sparkth plugins migrate create my_plugin "initial models"
   ```

4. **Review migration file**
   ```bash
   # Check generated file in app/migrations/versions/
   ls -la app/migrations/versions/
   ```

5. **Apply migration**
   ```bash
   sparkth plugins migrate apply
   ```

### Updating Models

1. **Modify model in plugin**
   ```python
   class Task(SQLModel, table=True):
       # ... existing fields ...
       priority: int = Field(default=1)  # New field
   ```

2. **Generate new migration**
   ```bash
   sparkth plugins migrate create my_plugin "add priority field"
   ```

3. **Apply migration**
   ```bash
   sparkth plugins migrate apply
   ```

## Foreign Keys to Core Tables

If your plugin needs to reference core app tables:

```python
class PluginModel(SQLModel, table=True):
    __tablename__ = "my_plugin_models"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Reference to core User table
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
```

**Note**: Be careful with foreign keys to ensure they don't break if core models change.

## Migration Files

### Location

All migrations (core + plugins) are stored in:
```
app/migrations/versions/
```

### Naming

Plugin migrations are prefixed with plugin name:
```
ABC123_tasks_plugin_add_task_model.py
```

### Manual Editing

You can manually edit migration files if needed:

```python
def upgrade():
    # Auto-generated
    op.create_table('tasks_plugin_tasks', ...)
    
    # Add custom SQL
    op.execute("CREATE INDEX idx_tasks_completed ON tasks_plugin_tasks(completed)")

def downgrade():
    op.drop_table('tasks_plugin_tasks')
```

## Best Practices

### 1. Always Namespace Tables

```python
✅ __tablename__ = "plugin_name_table_name"
❌ __tablename__ = "table_name"
```

### 2. Use Proper Field Types

```python
# String fields
name: str = Field(max_length=255)

# Optional fields
description: Optional[str] = None

# Timestamps
created_at: datetime = Field(default_factory=datetime.utcnow)

# Booleans
is_active: bool = Field(default=True)
```

### 3. Add Indexes for Performance

```python
class Task(SQLModel, table=True):
    __tablename__ = "tasks_plugin_tasks"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True)  # Add index
    status: str = Field(index=True)   # Add index
```

### 4. Document Your Models

```python
class Task(SQLModel, table=True):
    """
    Task model for the tasks plugin.
    
    Represents a user task with title, description, and completion status.
    """
    __tablename__ = "tasks_plugin_tasks"
    
    id: Optional[int] = Field(default=None, primary_key=True, description="Unique task ID")
    title: str = Field(max_length=255, description="Task title")
```

### 5. Test Migrations

Always test migrations in development before production:

```bash
# Create migration
sparkth plugins migrate create my_plugin "test change"

# Apply
sparkth plugins migrate apply

# Test app
uvicorn app.main:app --reload

# If issue, rollback
sparkth plugins migrate rollback
```

## Troubleshooting

### Migration Not Detecting Changes

**Problem**: Created new model but migration is empty.

**Solution**:
1. Ensure model is registered: `Filters.SQLMODEL_MODELS.add_item(MyModel)`
2. Ensure plugin is enabled: `sparkth plugins list`
3. Check model has `table=True` and `__tablename__`

### Table Already Exists Error

**Problem**: Migration fails with "table already exists"

**Solution**:
```bash
# Mark migration as applied without running it
alembic stamp head
```

### Foreign Key Constraint Failed

**Problem**: Can't create row due to foreign key

**Solution**:
1. Ensure referenced table exists
2. Check foreign key column name matches
3. Verify referenced row exists

### Model Not Found

**Problem**: `AttributeError: module has no attribute 'MyModel'`

**Solution**:
1. Ensure plugin is enabled
2. Check plugin file for syntax errors
3. Verify model is defined before registration

## Advanced Topics

### Multiple Models in One Plugin

```python
class Task(SQLModel, table=True):
    __tablename__ = "tasks_plugin_tasks"
    # ...

class TaskComment(SQLModel, table=True):
    __tablename__ = "tasks_plugin_comments"
    task_id: int = Field(foreign_key="tasks_plugin_tasks.id")
    # ...

# Register both
Filters.SQLMODEL_MODELS.add_items([Task, TaskComment])
```

### Relationships

```python
from sqlmodel import Relationship

class Task(SQLModel, table=True):
    __tablename__ = "tasks_plugin_tasks"
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Relationship to comments
    comments: list["TaskComment"] = Relationship(back_populates="task")

class TaskComment(SQLModel, table=True):
    __tablename__ = "tasks_plugin_comments"
    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks_plugin_tasks.id")
    
    # Back-reference
    task: Task = Relationship(back_populates="comments")
```

### Data Migrations

Sometimes you need to migrate data, not just schema:

```python
# In migration file
def upgrade():
    # Create table
    op.create_table(...)
    
    # Migrate data
    connection = op.get_bind()
    connection.execute(text("""
        INSERT INTO tasks_plugin_tasks (title)
        SELECT name FROM old_tasks
    """))
```

## See Also

- [Plugin System Documentation](PLUGIN_SYSTEM.md)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Example Tasks Plugin](examples/tasks_plugin.py)
