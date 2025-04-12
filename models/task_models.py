# app/models/task_models.py
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import List, Optional
from datetime import datetime, timezone

class TaskBase(BaseModel):
    originalInput: str
    processedDescription: Optional[str] = None
    priority: Optional[str] = None # e.g., 'High', 'Medium', 'Low'
    tags: Optional[List[str]] = []
    deadline: datetime # Now mandatory

    @field_validator('deadline', mode='before')
    def ensure_timezone_awareness(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            # Assuming UTC if timezone is naive
            return value.replace(tzinfo=timezone.utc)
        # If it's already a string (like from Firestore), Pydantic will handle parsing
        # If it's already timezone-aware, return as is
        return value

class TaskCreate(BaseModel):
    rawInput: str = Field(..., min_length=1)
    deadline: Optional[datetime] = None # Allow explicit deadline setting

    @field_validator('deadline', mode='before')
    def ensure_timezone_awareness_create(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

class TaskRead(TaskBase):
    id: str
    userId: str # Keep track of owner
    createdAt: datetime
    updatedAt: datetime
    completed: bool

class TaskInDB(TaskBase):
    # Fields as stored in Firestore
    userId: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)
    completed: bool = False

# Model for data expected back from AI service
class ProcessedTaskData(BaseModel):
    processed_description: Optional[str] = None
    deadline: Optional[datetime] = None # AI should return structured datetime now
    tags: Optional[List[str]] = []
    priority_suggestion: Optional[str] = None

    @field_validator('deadline', mode='before')
    def ensure_timezone_awareness_ai(cls, value):
        # Add validation/conversion if AI might return strings or naive datetimes
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        # Add parsing logic if AI returns date strings
        # Example: if isinstance(value, str): return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
        return value
