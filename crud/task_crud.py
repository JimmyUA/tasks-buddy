from google.cloud import firestore
from google.cloud.firestore import Query # Import Query
from typing import List, Dict, Any
from datetime import datetime
from core.config import settings
from models.task_models import TaskInDB, ProcessedTaskData, TaskRead

# Initialize Firestore client
# Uses GOOGLE_APPLICATION_CREDENTIALS environment variable implicitly
try:
    db = firestore.AsyncClient(project=settings.gcp_project_id)
    print("Firestore AsyncClient Initialized successfully.")
except Exception as e:
    print(f"Error initializing Firestore client: {e}")
    db = None # Set db to None or handle error as appropriate

async def create_task(user_id: str, raw_input: str, processed_data: ProcessedTaskData) -> TaskRead:
    """Creates a new task document in Firestore."""
    if not db:
        raise ConnectionError("Firestore client not initialized")

    timestamp = datetime.utcnow()
    new_task_data = TaskInDB(
        userId=user_id,
        originalInput=raw_input,
        processedDescription=processed_data.processed_description or raw_input, # Use raw if processing failed
        priority=processed_data.priority_suggestion or 'Medium', # Default priority
        tags=processed_data.tags or [],
        dueDateHint=processed_data.due_date_hint,
        createdAt=timestamp,
        updatedAt=timestamp
    )

    # Convert Pydantic model to dict for Firestore
    task_dict = new_task_data.model_dump(exclude_none=True)

    # Add the document with an auto-generated ID
    doc_ref = await db.collection(settings.tasks_collection).add(task_dict)
    # doc_ref is a tuple: (commit_time, document_reference)
    document_id = doc_ref[1].id

    # Return the created task including its ID
    return TaskRead(id=document_id, **task_dict) # Use the dict we just added

async def get_tasks_for_user(user_id: str) -> List[TaskRead]:
    """Retrieves all tasks for a specific user, sorted by priority then creation date."""
    if not db:
        raise ConnectionError("Firestore client not initialized")

    tasks_ref = db.collection(settings.tasks_collection).where(filter=firestore.FieldFilter("userId", "==", user_id))

    # Firestore doesn't easily support multi-field sorting where one field might be null or non-numeric priority strings.
    # Fetch all user's tasks and sort them in the application layer for flexibility.
    # For larger datasets, you might need to introduce a numeric priority field or use denormalization.

    docs_stream = tasks_ref.stream()
    tasks = []
    async for doc in docs_stream:
        task_data = doc.to_dict()
        task_data['id'] = doc.id # Add the document ID
        # Ensure datetime fields are handled correctly (Firestore might return them)
        if isinstance(task_data.get('createdAt'), firestore.SERVER_TIMESTAMP.__class__):
             task_data['createdAt'] = datetime.utcnow() # Approximation if server timestamp
        if isinstance(task_data.get('updatedAt'), firestore.SERVER_TIMESTAMP.__class__):
            task_data['updatedAt'] = datetime.utcnow()

        # Validate and parse into TaskRead model
        try:
             tasks.append(TaskRead(**task_data))
        except Exception as e:
            print(f"Error parsing task data from Firestore (ID: {doc.id}): {e} - Data: {task_data}")


    # --- Sorting Logic (matches frontend request) ---
    priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
    def sort_key(task: TaskRead):
        prio_value = priority_order.get(task.priority, 99) # Tasks without priority go last
        created_timestamp = task.createdAt.timestamp() if task.createdAt else 0
        # Sort by priority (ascending value = higher prio), then by creation time (descending = newest first)
        return (prio_value, -created_timestamp)

    tasks.sort(key=sort_key)
    # --- End Sorting Logic ---

    return tasks