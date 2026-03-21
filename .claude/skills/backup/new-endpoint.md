# /new-endpoint - Create New API Endpoint

Scaffold a new API endpoint following the project's patterns.

## Usage

`/new-endpoint <resource_name>`

Example: `/new-endpoint notifications`

## Instructions

When the user runs this skill, create the following files:

### 1. Model (app/models/{resource}.py)

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.database import Base


class {Resource}(Base):
    __tablename__ = "{resources}"

    id = Column(Integer, primary_key=True, index=True)
    # Add fields here
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 2. Schema (app/schemas/{resource}.py)

```python
from pydantic import BaseModel
from datetime import datetime


class {Resource}Base(BaseModel):
    # Add fields here
    pass


class {Resource}Create({Resource}Base):
    pass


class {Resource}Response({Resource}Base):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
```

### 3. Route (app/api/routes/{resource}.py)

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.{resource} import {Resource}
from app.schemas.{resource} import {Resource}Create, {Resource}Response
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/{resources}", tags=["{Resources}"])


@router.get("/", response_model=list[{Resource}Response])
def list_{resources}(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query({Resource}).all()


@router.post("/", response_model={Resource}Response, status_code=status.HTTP_201_CREATED)
def create_{resource}(
    data: {Resource}Create,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    {resource} = {Resource}(**data.model_dump())
    db.add({resource})
    db.commit()
    db.refresh({resource})
    return {resource}


@router.get("/{id}", response_model={Resource}Response)
def get_{resource}(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    {resource} = db.query({Resource}).filter({Resource}.id == id).first()
    if not {resource}:
        raise HTTPException(status_code=404, detail="{Resource} not found")
    return {resource}
```

### 4. Register in main.py

Add the import and include the router:

```python
from app.api.routes import {resource}

app.include_router({resource}.router, prefix="/api")
```

### 5. Export in models/__init__.py

```python
from app.models.{resource} import {Resource}
```

## After Creation

- Restart the backend server to pick up new routes
- Access API docs at http://localhost:8000/docs to see new endpoints
