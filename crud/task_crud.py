from google.cloud import firestore
from google.cloud.firestore import Query
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from typing import List, Dict, Any
from datetime import datetime, timezone # Ensure timezone is imported
from core.config import settings
from models.task_models import TaskInDB, ProcessedTaskData, TaskRead, TaskCreate

# Initialize Firestore client
try:
    db = firestore.AsyncClient(project=settings.gcp_project_id)
    print("Firestore AsyncClient Initialized successfully.")
except Exception as e:
    print(f"Error initializing Firestore client: {e}")
    db = None

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

async def create_task(user_id: str, task_in: TaskCreate, processed_data: ProcessedTaskData) -> TaskRead:
    """Creates a new task document in Firestore. Requires a deadline."""
    tasks_collection = await get_tasks_collection()

    # Determine the deadline: use provided one first, then AI, else raise error
    final_deadline = None
    if task_in.deadline:
        final_deadline = task_in.deadline
        print(f"Using deadline provided by user: {final_deadline}")
    elif processed_data.deadline:
        final_deadline = processed_data.deadline
        print(f"Using deadline extracted by AI: {final_deadline}")
    else:
        # This case should now be handled by the endpoint before calling create_task
        # but raising here provides a safety net.
        raise ValueError("Task creation failed: Deadline is required but was not provided or detected by AI.")

    # Ensure deadline is timezone-aware (redundant if validators work, but safe)
    if final_deadline.tzinfo is None:
        final_deadline = final_deadline.replace(tzinfo=timezone.utc)

    timestamp = datetime.now(timezone.utc) # Use timezone-aware now
    new_task_data = TaskInDB(
        userId=user_id,
        originalInput=task_in.rawInput,
        processedDescription=processed_data.processed_description or task_in.rawInput,
        priority=processed_data.priority_suggestion or 'Medium',
        tags=processed_data.tags or [],
        deadline=final_deadline, # Use the determined deadline
        createdAt=timestamp,
        updatedAt=timestamp,
        completed=False
    )

    # Convert Pydantic model to dict for Firestore
    task_dict = new_task_data.model_dump(exclude_none=True)

    # Add the document
    commit_time, doc_ref = await tasks_collection.add(task_dict)
    document_id = doc_ref.id

    # Return the created task including its ID
    return TaskRead(id=document_id, **task_dict)

async def get_tasks_for_user(user_id: str) -> List[TaskRead]:
    """Retrieves all tasks for a specific user, sorted."""
    tasks_collection = await get_tasks_collection()
    tasks_ref = tasks_collection.where(filter=firestore.FieldFilter("userId", "==", user_id))
    docs_stream = tasks_ref.stream()
    tasks = []
    async for doc in docs_stream:
        task_data = doc.to_dict()
        task_data['id'] = doc.id
        # Ensure datetime fields are timezone-aware upon reading
        if isinstance(task_data.get('createdAt'), datetime) and task_data['createdAt'].tzinfo is None:
            task_data['createdAt'] = task_data['createdAt'].replace(tzinfo=timezone.utc)
        if isinstance(task_data.get('updatedAt'), datetime) and task_data['updatedAt'].tzinfo is None:
            task_data['updatedAt'] = task_data['updatedAt'].replace(tzinfo=timezone.utc)
        if isinstance(task_data.get('deadline'), datetime) and task_data['deadline'].tzinfo is None:
            task_data['deadline'] = task_data['deadline'].replace(tzinfo=timezone.utc)

        try:
            tasks.append(TaskRead(**task_data))
        except Exception as e:
            print(f"Error parsing task data from Firestore (ID: {doc.id}): {e} - Data: {task_data}")

    priority_order = {'High': 1, 'Medium': 2, 'Low': 3}
    def sort_key(task: TaskRead):
        prio_value = priority_order.get(task.priority, 99)
        # Ensure deadline is used for sorting if createdAt is ambiguous/same
        created_timestamp = task.createdAt.timestamp() if task.createdAt else 0
        deadline_timestamp = task.deadline.timestamp() if task.deadline else float('inf') # Sort tasks without deadline last
        # Sort by priority, then deadline (ascending), then creation (descending)
        return (prio_value, deadline_timestamp, -created_timestamp)

    tasks.sort(key=sort_key)
    return tasks

async def update_task_completion(task_id: str, completed: bool) -> TaskRead:
    """Updates the completion status of a task."""
    tasks_collection = await get_tasks_collection()
    task_ref = tasks_collection.document(task_id)
    try:
        await task_ref.update({"completed": completed, "updatedAt": datetime.now(timezone.utc)})
        updated_doc = await task_ref.get()
        if updated_doc.exists:
            task_data = updated_doc.to_dict()
            # Ensure deadline timezone awareness on read during update
            if isinstance(task_data.get('deadline'), datetime) and task_data['deadline'].tzinfo is None:
                 task_data['deadline'] = task_data['deadline'].replace(tzinfo=timezone.utc)
            return TaskRead(id=updated_doc.id, **task_data)
        else:
            raise ValueError(f"Task with ID {task_id} not found after update attempt.")
    except Exception as e:
        print(f"Error updating task completion status: {e}")
        raise
