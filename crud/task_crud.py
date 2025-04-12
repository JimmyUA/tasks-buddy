from google.cloud import firestore
from google.cloud.firestore import Query # Import Query
from google.cloud.firestore_v1.base_document import DocumentSnapshot
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

async def get_tasks_collection():
    """Returns the Firestore collection reference for tasks."""
    if not db:
        raise ConnectionError("Firestore client not initialized")
    return db.collection(settings.tasks_collection)

async def get_task(task_id: str) -> DocumentSnapshot:
    """Fetches a single task document by its ID."""
    tasks_collection = await get_tasks_collection()
    task_ref = tasks_collection.document(task_id)
    task_doc = await task_ref.get()
    return task_doc

async def create_task(user_id: str, raw_input: str, processed_data: ProcessedTaskData) -> TaskRead:
    """Creates a new task document in Firestore."""
    tasks_collection = await get_tasks_collection()

    timestamp = datetime.utcnow()
    new_task_data = TaskInDB(
        userId=user_id,
        originalInput=raw_input,
        processedDescription=processed_data.processed_description or raw_input, # Use raw if processing failed
        priority=processed_data.priority_suggestion or 'Medium', # Default priority
        tags=processed_data.tags or [],
        dueDateHint=processed_data.due_date_hint,
        createdAt=timestamp,
        updatedAt=timestamp,
        completed=False
    )

    # Convert Pydantic model to dict for Firestore
    task_dict = new_task_data.model_dump(exclude_none=True)

    # Add the document with an auto-generated ID
    commit_time, doc_ref = await tasks_collection.add(task_dict)
    document_id = doc_ref.id

    # Return the created task including its ID
    return TaskRead(id=document_id, **task_dict) # Use the dict we just added

async def get_tasks_for_user(user_id: str) -> List[TaskRead]:
    """Retrieves all tasks for a specific user, sorted by priority then creation date."""
    tasks_collection = await get_tasks_collection()

    tasks_ref = tasks_collection.where(filter=firestore.FieldFilter("userId", "==", user_id))

    # Fetch all user's tasks and sort them in the application layer for flexibility.
    docs_stream = tasks_ref.stream()
    tasks = []
    async for doc in docs_stream:
        task_data = doc.to_dict()
        task_data['id'] = doc.id # Add the document ID
        # Ensure datetime fields are handled correctly
        if isinstance(task_data.get('createdAt'), firestore.SERVER_TIMESTAMP.__class__):
             task_data['createdAt'] = datetime.utcnow() # Approximation
        if isinstance(task_data.get('updatedAt'), firestore.SERVER_TIMESTAMP.__class__):
            task_data['updatedAt'] = datetime.utcnow()

        # Validate and parse into TaskRead model
        try:
             tasks.append(TaskRead(**task_data))
        except Exception as e:
            print(f"Error parsing task data from Firestore (ID: {doc.id}): {e} - Data: {task_data}")

    # --- Sorting Logic ---
    priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
    def sort_key(task: TaskRead):
        prio_value = priority_order.get(task.priority, 99)
        created_timestamp = task.createdAt.timestamp() if task.createdAt else 0
        return (prio_value, -created_timestamp)

    tasks.sort(key=sort_key)
    # --- End Sorting Logic ---

    return tasks

async def update_task_completion(task_id: str, completed: bool) -> TaskRead:
    """Updates the completion status of a task."""
    tasks_collection = await get_tasks_collection()
    task_ref = tasks_collection.document(task_id)
    try:
        await task_ref.update({"completed": completed, "updatedAt": datetime.utcnow()})
        updated_doc = await task_ref.get()
        if updated_doc.exists:
            task_data = updated_doc.to_dict()
            return TaskRead(id=updated_doc.id, **task_data)
        else:
            # This case should ideally not be reached if get_task in the endpoint worked,
            # but added for robustness.
            raise ValueError(f"Task with ID {task_id} not found after update attempt.")
    except Exception as e:
        print(f"Error updating task completion status: {e}")
        raise
