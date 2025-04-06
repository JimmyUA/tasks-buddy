# app/models/task_models.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class TaskBase(BaseModel):
    originalInput: str
    processedDescription: Optional[str] = None
    priority: Optional[str] = None # e.g., 'High', 'Medium', 'Low'
    tags: Optional[List[str]] = []
    dueDateHint: Optional[str] = None # Text hint from AI, not structured date yet

class TaskCreate(BaseModel):
    rawInput: str = Field(..., min_length=1)

class TaskRead(TaskBase):
    id: str
    userId: str # Keep track of owner
    createdAt: datetime
    updatedAt: datetime

class TaskInDB(TaskBase):
    # Fields as stored in Firestore
    userId: str
    createdAt: datetime = Field(default_factory=datetime.utcnow)
    updatedAt: datetime = Field(default_factory=datetime.utcnow)

# Model for data expected back from AI service
class ProcessedTaskData(BaseModel):
    processed_description: Optional[str] = None
    due_date_hint: Optional[str] = None
    tags: Optional[List[str]] = []
    priority_suggestion: Optional[str] = None