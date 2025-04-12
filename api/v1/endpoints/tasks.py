# app/api/v1/endpoints/tasks.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict
from models.task_models import TaskCreate, TaskRead, TaskInDB
from services import ai_service, auth_service
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from crud import task_crud
from core.config import settings

router = APIRouter()

@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_new_task(
    task_in: TaskCreate,
    current_user_id: str = Depends(auth_service.get_current_user)
):
    """
    Receives raw task input, processes it with AI, applies basic overrides,
    and saves it to Firestore.
    """
    print(f"Received raw input from user {current_user_id}: {task_in.rawInput}")
    try:
        # 1. Process with AI
        processed_data = await ai_service.process_raw_task_input(task_in.rawInput)
        print(f"AI Processed Data: {processed_data}")

        # 2. Apply simple keyword-based priority boost (MVP preference logic)
        final_priority = processed_data.priority_suggestion or 'Medium'
        raw_input_lower = task_in.rawInput.lower()
        if any(keyword in raw_input_lower for keyword in settings.high_priority_keywords):
            print(f"Keyword match found. Overriding priority to High.")
            final_priority = 'High'
        processed_data.priority_suggestion = final_priority # Update the object passed to CRUD

        # 3. Save to Database
        created_task = await task_crud.create_task(
            user_id=current_user_id,
            raw_input=task_in.rawInput,
            processed_data=processed_data
        )
        print(f"Task created successfully (ID: {created_task.id})")
        return created_task

    except ConnectionError as e:
         print(f"Database connection error: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service is unavailable.")
    except Exception as e:
        print(f"Error creating task: {e}")
        # Log the full exception traceback here in a real app
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create task.")


@router.get("/", response_model=List[TaskRead])
async def read_user_tasks(
    current_user_id: str = Depends(auth_service.get_current_user)
):
    """
    Retrieves all tasks for the currently authenticated user, sorted.
    """
    print(f"Fetching tasks for user {current_user_id}")
    try:
        tasks = await task_crud.get_tasks_for_user(user_id=current_user_id)
        print(f"Retrieved {len(tasks)} tasks for user {current_user_id}")
        return tasks
    except ConnectionError as e:
         print(f"Database connection error: {e}")
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service is unavailable.")
    except Exception as e:
        print(f"Error reading tasks: {e}")
        # Log the full exception traceback here
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve tasks.")


@router.put("/{task_id}/complete", response_model=TaskRead)
async def update_task_completion(
    task_id: str,
    completed: Dict[str, bool],
    current_user_id: str = Depends(auth_service.get_current_user)
):
    """
    Updates the completion status of a specific task.
    """
    print(f"Updating completion status for task {task_id} to {completed} by user {current_user_id}")
    try:
        # Fetch the task to ensure it exists and belongs to the user
        task_doc: DocumentSnapshot = await task_crud.get_task(task_id)
        if not task_doc.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        task_data = task_doc.to_dict()
        if task_data["userId"] != current_user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify this task.")

        updated_task = await task_crud.update_task_completion(task_id=task_id, completed=completed.get("completed"))
        print(f"Task {task_id} completion status updated to {completed.get("completed")}")
        return updated_task
    except ConnectionError as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service is unavailable.")
    except Exception as e:
        print(f"Error updating task completion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update task completion status.")
